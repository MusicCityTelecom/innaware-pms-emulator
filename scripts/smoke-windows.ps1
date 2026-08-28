param(
    [string]$Exe = ".\dist-windows\InnAware-PMS-Emulator.exe",
    [int]$Port = 18081
)

$ErrorActionPreference = "Stop"
$Exe = (Resolve-Path $Exe).Path
$TempData = Join-Path $env:TEMP ("innaware-pms-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $TempData | Out-Null

$OldDataDir = $env:INNAWARE_PMS_DATA_DIR
$env:INNAWARE_PMS_DATA_DIR = $TempData
$Process = $null
$LogPath = Join-Path $TempData "logs\emulator.log"
$TaskKill = Join-Path $env:SystemRoot "System32\taskkill.exe"

# Never let build/smoke runs count as production usage telemetry.
$UpdateDir = Join-Path $TempData "updates"
New-Item -ItemType Directory -Force -Path $UpdateDir | Out-Null
@{
    check_app_updates_on_start = $false
    check_protocol_updates_on_start = $false
    include_prereleases = $true
    send_anonymous_usage_statistics = $false
} | ConvertTo-Json | Set-Content -Path (Join-Path $UpdateDir "settings.json") -Encoding UTF8

function Show-SmokeLog {
    if (Test-Path $LogPath) {
        Write-Host ""
        Write-Host "===== FROZEN EXE DIAGNOSTIC LOG =====" -ForegroundColor Yellow
        Get-Content -Path $LogPath -Tail 120 -ErrorAction SilentlyContinue
        Write-Host "===== END DIAGNOSTIC LOG =====" -ForegroundColor Yellow
    }
    else { Write-Host "No frozen-EXE diagnostic log was created at $LogPath" -ForegroundColor Yellow }
}

function Get-SmokeProcesses {
    $Expected = [System.IO.Path]::GetFullPath($Exe)
    try {
        return @(Get-CimInstance Win32_Process -Filter "Name='InnAware-PMS-Emulator.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.ExecutablePath -and ([System.IO.Path]::GetFullPath($_.ExecutablePath) -ieq $Expected) })
    }
    catch { return @() }
}

function Stop-SmokeProcessTree {
    param([int]$RootPid)
    if ($RootPid -gt 0 -and (Test-Path $TaskKill)) { & $TaskKill /PID $RootPid /T /F 2>$null | Out-Null }
    foreach ($Item in @(Get-SmokeProcesses)) {
        if (Test-Path $TaskKill) { & $TaskKill /PID $Item.ProcessId /T /F 2>$null | Out-Null }
        else { Stop-Process -Id $Item.ProcessId -Force -ErrorAction SilentlyContinue }
    }
    for ($i = 0; $i -lt 50; $i++) {
        if (@(Get-SmokeProcesses).Count -eq 0) { return }
        Start-Sleep -Milliseconds 100
    }
    $Remaining = @(Get-SmokeProcesses | ForEach-Object { $_.ProcessId })
    if ($Remaining.Count -gt 0) { Write-Warning "Frozen smoke-test process(es) still present after cleanup: $($Remaining -join ', ')" }
}

try {
    Write-Host "Starting frozen EXE smoke test on 127.0.0.1:$Port" -ForegroundColor Cyan
    $Process = Start-Process `
        -FilePath $Exe `
        -ArgumentList @("--server-only", "--host", "127.0.0.1", "--port", "$Port", "--log-level", "warning") `
        -WindowStyle Hidden `
        -PassThru

    $Ready = $false
    for ($i = 0; $i -lt 100; $i++) {
        if ($Process.HasExited) { throw "Frozen executable exited before the API became ready. Exit code: $($Process.ExitCode)" }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/health" -TimeoutSec 1
            if ($health.status -eq "ok") { $Ready = $true; break }
        }
        catch { Start-Sleep -Milliseconds 150 }
    }
    if (-not $Ready) { throw "Frozen executable did not become healthy within the smoke-test timeout." }

    $info = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/app-info" -TimeoutSec 3
    if ($info.product -ne "InnAware PMS Emulator") { throw "Unexpected app-info product value." }
    if (-not $info.protocol_pack_version -or $info.protocol_pack_version -eq "unknown") { throw "Frozen build could not resolve its bundled protocol-pack version." }

    $telemetry = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/telemetry/status" -TimeoutSec 3
    if ($telemetry.enabled) { throw "Frozen smoke test expected telemetry to be disabled by its persisted smoke settings." }
    $ParsedUuid = [guid]::Empty
    if (-not [guid]::TryParse([string]$telemetry.install_id, [ref]$ParsedUuid)) { throw "Frozen build telemetry install UUID is invalid." }
    if ($telemetry.protocol_pack_version -ne $info.protocol_pack_version) { throw "Telemetry and app-info disagree about the active protocol-pack version." }

    $profiles = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/profiles" -TimeoutSec 3
    $profileIds = @($profiles.profiles | ForEach-Object { $_.id })
    foreach ($required in @("fias-pms-tcp-server", "hilton-pep-fias-tcp-server", "innform-xl-tcp-server", "hobis-a-tcp-server")) {
        if ($profileIds -notcontains $required) { throw "Required technician profile missing from frozen build: $required" }
    }

    $property = Invoke-RestMethod `
        -Method Post `
        -Uri "http://127.0.0.1:$Port/api/v1/scenarios/small-hotel?property_id=windows-smoke" `
        -TimeoutSec 5

    $RoomNames = @($property.rooms.PSObject.Properties | ForEach-Object { $_.Name })
    $RoomCount = $RoomNames.Count
    Write-Host "Frozen demo property rooms: $RoomCount" -ForegroundColor DarkGray
    if ($RoomCount -ne 30) { throw "Frozen build demo property contained $RoomCount rooms; expected 30." }
    foreach ($RequiredRoom in @("101", "102", "103", "310")) {
        if ($RoomNames -notcontains $RequiredRoom) { throw "Frozen build demo property is missing expected room $RequiredRoom." }
    }

    $bundlePath = Join-Path $TempData "support.zip"
    Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/v1/support-bundle" -OutFile $bundlePath -TimeoutSec 10
    if (-not (Test-Path $bundlePath)) { throw "Support bundle was not produced by the frozen build." }
    if ((Get-Item $bundlePath).Length -lt 100) { throw "Support bundle from frozen build is unexpectedly small." }

    Write-Host "Frozen EXE smoke test PASS" -ForegroundColor Green
}
catch { Show-SmokeLog; throw }
finally {
    if ($Process) { Stop-SmokeProcessTree -RootPid $Process.Id }
    if ($null -eq $OldDataDir) { Remove-Item Env:INNAWARE_PMS_DATA_DIR -ErrorAction SilentlyContinue }
    else { $env:INNAWARE_PMS_DATA_DIR = $OldDataDir }
    Remove-Item -Recurse -Force $TempData -ErrorAction SilentlyContinue
}

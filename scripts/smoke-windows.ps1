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

function Show-SmokeLog {
    if (Test-Path $LogPath) {
        Write-Host "" 
        Write-Host "===== FROZEN EXE DIAGNOSTIC LOG =====" -ForegroundColor Yellow
        Get-Content -Path $LogPath -Tail 120 -ErrorAction SilentlyContinue
        Write-Host "===== END DIAGNOSTIC LOG =====" -ForegroundColor Yellow
    }
    else {
        Write-Host "No frozen-EXE diagnostic log was created at $LogPath" -ForegroundColor Yellow
    }
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
        if ($Process.HasExited) {
            throw "Frozen executable exited before the API became ready. Exit code: $($Process.ExitCode)"
        }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/health" -TimeoutSec 1
            if ($health.status -eq "ok") {
                $Ready = $true
                break
            }
        }
        catch {
            Start-Sleep -Milliseconds 150
        }
    }
    if (-not $Ready) { throw "Frozen executable did not become healthy within the smoke-test timeout." }

    $info = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/app-info" -TimeoutSec 3
    if ($info.product -ne "InnAware PMS Emulator") { throw "Unexpected app-info product value." }

    $profiles = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/profiles" -TimeoutSec 3
    $profileIds = @($profiles.profiles | ForEach-Object { $_.id })
    foreach ($required in @("fias-pms-tcp-server", "hilton-pep-fias-tcp-server", "innform-xl-tcp-server", "hobis-a-tcp-server")) {
        if ($profileIds -notcontains $required) { throw "Required technician profile missing from frozen build: $required" }
    }

    $property = Invoke-RestMethod `
        -Method Post `
        -Uri "http://127.0.0.1:$Port/api/v1/scenarios/small-hotel?property_id=windows-smoke" `
        -TimeoutSec 5
    if ($property.rooms.PSObject.Properties.Count -ne 30) { throw "Frozen build demo property did not contain 30 rooms." }

    $bundlePath = Join-Path $TempData "support.zip"
    Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/v1/support-bundle" -OutFile $bundlePath -TimeoutSec 10
    if (-not (Test-Path $bundlePath)) { throw "Support bundle was not produced by the frozen build." }
    if ((Get-Item $bundlePath).Length -lt 100) { throw "Support bundle from frozen build is unexpectedly small." }

    Write-Host "Frozen EXE smoke test PASS" -ForegroundColor Green
}
catch {
    Show-SmokeLog
    throw
}
finally {
    if ($Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        $Process.WaitForExit(5000) | Out-Null
    }
    if ($null -eq $OldDataDir) {
        Remove-Item Env:INNAWARE_PMS_DATA_DIR -ErrorAction SilentlyContinue
    }
    else {
        $env:INNAWARE_PMS_DATA_DIR = $OldDataDir
    }
    Remove-Item -Recurse -Force $TempData -ErrorAction SilentlyContinue
}

param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string]$SourceSha,

    [Parameter(Mandatory = $true)]
    [string]$Exe,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{64}$')]
    [string]$ExpectedExeSha256,

    [Parameter(Mandatory = $true)]
    [string]$NativeScreenshot,

    [Parameter(Mandatory = $true)]
    [string]$BrowserScreenshot,

    [string]$Output = ".\windows-acceptance.json",
    [int]$NativePort = 18081,
    [int]$BrowserPort = 18082,
    [int]$ReadyTimeoutSeconds = 30,
    [int]$ScreenshotTimeoutSeconds = 300
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Exe = (Resolve-Path $Exe).Path
$ExpectedExeSha256 = $ExpectedExeSha256.ToLowerInvariant()
$ActualExeSha256 = (Get-FileHash -Path $Exe -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualExeSha256 -ne $ExpectedExeSha256) {
    throw "Candidate EXE hash mismatch. Expected $ExpectedExeSha256 but found $ActualExeSha256."
}

if ($NativePort -eq $BrowserPort) {
    throw "NativePort and BrowserPort must be different."
}
foreach ($Port in @($NativePort, $BrowserPort)) {
    if ($Port -lt 1 -or $Port -gt 65535) {
        throw "Acceptance ports must be between 1 and 65535."
    }
}

$TaskKill = Join-Path $env:SystemRoot "System32\taskkill.exe"
$OriginalDataDir = $env:INNAWARE_PMS_DATA_DIR
$TempRoots = New-Object System.Collections.Generic.List[string]

function Get-CandidateProcesses {
    $ExpectedPath = [System.IO.Path]::GetFullPath($Exe)
    try {
        return @(Get-CimInstance Win32_Process -Filter "Name='InnAware-PMS-Emulator.exe'" -ErrorAction SilentlyContinue |
            Where-Object {
                $_.ExecutablePath -and
                ([System.IO.Path]::GetFullPath($_.ExecutablePath) -ieq $ExpectedPath)
            })
    }
    catch {
        return @()
    }
}

function Stop-CandidateProcessTree {
    param([int]$RootPid)

    if ($RootPid -gt 0 -and (Test-Path $TaskKill)) {
        & $TaskKill /PID $RootPid /T /F 2>$null | Out-Null
    }

    foreach ($Item in @(Get-CandidateProcesses)) {
        if (Test-Path $TaskKill) {
            & $TaskKill /PID $Item.ProcessId /T /F 2>$null | Out-Null
        }
        else {
            Stop-Process -Id $Item.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }

    for ($i = 0; $i -lt 60; $i++) {
        if (@(Get-CandidateProcesses).Count -eq 0) {
            return
        }
        Start-Sleep -Milliseconds 100
    }

    $Remaining = @(Get-CandidateProcesses | ForEach-Object { $_.ProcessId })
    if ($Remaining.Count -gt 0) {
        throw "Candidate Emulator process(es) remained after shutdown: $($Remaining -join ', ')."
    }
}

function New-AcceptanceDataDir {
    param([string]$Surface)

    $Root = Join-Path $env:TEMP ("innaware-pms-field-acceptance-$Surface-" + [guid]::NewGuid().ToString("N"))
    $UpdateDir = Join-Path $Root "updates"
    New-Item -ItemType Directory -Force -Path $UpdateDir | Out-Null
    $TempRoots.Add($Root) | Out-Null

    $Settings = [ordered]@{
        check_app_updates_on_start = $false
        check_protocol_updates_on_start = $false
        include_prereleases = $true
        send_anonymous_usage_statistics = $false
    }
    $Settings | ConvertTo-Json | Set-Content -Path (Join-Path $UpdateDir "settings.json") -Encoding UTF8

    $RoundTrip = Get-Content -Raw -Path (Join-Path $UpdateDir "settings.json") | ConvertFrom-Json
    if ($RoundTrip.check_app_updates_on_start -ne $false -or
        $RoundTrip.check_protocol_updates_on_start -ne $false -or
        $RoundTrip.send_anonymous_usage_statistics -ne $false) {
        throw "Disposable acceptance settings did not persist the required telemetry/update suppression."
    }

    return $Root
}

function Wait-ForHealthyApi {
    param(
        [System.Diagnostics.Process]$Process,
        [int]$Port
    )

    $Deadline = [DateTime]::UtcNow.AddSeconds($ReadyTimeoutSeconds)
    while ([DateTime]::UtcNow -lt $Deadline) {
        if ($Process.HasExited) {
            throw "Candidate executable exited before 127.0.0.1:$Port became healthy. Exit code: $($Process.ExitCode)."
        }
        try {
            $Health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/health" -TimeoutSec 1
            if ($Health.status -eq "ok") {
                return $Health
            }
        }
        catch {
            Start-Sleep -Milliseconds 200
        }
    }
    throw "Candidate executable did not become healthy on 127.0.0.1:$Port within $ReadyTimeoutSeconds seconds."
}

function Wait-ForFreshScreenshot {
    param(
        [string]$Path,
        [string]$Surface
    )

    $FullPath = [System.IO.Path]::GetFullPath($Path)
    $Parent = Split-Path -Parent $FullPath
    if ($Parent) {
        New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    }
    if (Test-Path $FullPath) {
        Remove-Item -Force $FullPath
    }

    Write-Host ""
    Write-Host "Capture the $Surface console now and save the screenshot to:" -ForegroundColor Yellow
    Write-Host "  $FullPath" -ForegroundColor Cyan
    Write-Host "The harness will wait up to $ScreenshotTimeoutSeconds seconds for a fresh screenshot file." -ForegroundColor DarkGray

    $Deadline = [DateTime]::UtcNow.AddSeconds($ScreenshotTimeoutSeconds)
    while ([DateTime]::UtcNow -lt $Deadline) {
        if (Test-Path $FullPath) {
            $Item = Get-Item $FullPath
            if ($Item.Length -ge 1024) {
                return [ordered]@{
                    path = $FullPath
                    size_bytes = [int64]$Item.Length
                    sha256 = (Get-FileHash -Path $FullPath -Algorithm SHA256).Hash.ToLowerInvariant()
                }
            }
        }
        Start-Sleep -Milliseconds 250
    }

    throw "No usable fresh $Surface screenshot appeared at $FullPath within $ScreenshotTimeoutSeconds seconds."
}

function Invoke-AcceptanceSurface {
    param(
        [ValidateSet('native_gui', 'browser')]
        [string]$Surface,
        [int]$Port,
        [string]$ScreenshotPath
    )

    if (@(Get-CandidateProcesses).Count -ne 0) {
        throw "A candidate Emulator process is already running. Close it before starting $Surface acceptance."
    }

    $DataDir = New-AcceptanceDataDir -Surface $Surface
    $env:INNAWARE_PMS_DATA_DIR = $DataDir
    $Process = $null

    $Arguments = @("--host", "127.0.0.1", "--port", "$Port", "--log-level", "warning")
    if ($Surface -eq "browser") {
        $Arguments = @("--browser") + $Arguments
    }

    try {
        Write-Host "Starting $Surface acceptance on 127.0.0.1:$Port" -ForegroundColor Cyan
        $Process = Start-Process -FilePath $Exe -ArgumentList $Arguments -PassThru
        $Health = Wait-ForHealthyApi -Process $Process -Port $Port

        $Info = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/app-info" -TimeoutSec 3
        if ($Info.product -ne "InnAware PMS Emulator") {
            throw "$Surface returned unexpected app-info product '$($Info.product)'."
        }

        $Telemetry = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/telemetry/status" -TimeoutSec 3
        if ($Telemetry.enabled) {
            throw "$Surface acceptance requires telemetry to remain disabled."
        }

        $Screenshot = Wait-ForFreshScreenshot -Path $ScreenshotPath -Surface $Surface

        return [ordered]@{
            result = "pass"
            health_status = [string]$Health.status
            app_info_product = [string]$Info.product
            app_info_version = [string]$Info.version
            protocol_pack_version = [string]$Info.protocol_pack_version
            management_endpoint = "http://127.0.0.1:$Port/"
            screenshot_sha256 = [string]$Screenshot.sha256
            screenshot_size_bytes = [int64]$Screenshot.size_bytes
        }
    }
    finally {
        if ($Process) {
            Stop-CandidateProcessTree -RootPid $Process.Id
        }
        else {
            Stop-CandidateProcessTree -RootPid 0
        }
        if ($null -eq $OriginalDataDir) {
            Remove-Item Env:INNAWARE_PMS_DATA_DIR -ErrorAction SilentlyContinue
        }
        else {
            $env:INNAWARE_PMS_DATA_DIR = $OriginalDataDir
        }
    }
}

try {
    $Native = Invoke-AcceptanceSurface -Surface "native_gui" -Port $NativePort -ScreenshotPath $NativeScreenshot
    $Browser = Invoke-AcceptanceSurface -Surface "browser" -Port $BrowserPort -ScreenshotPath $BrowserScreenshot

    $Remaining = @(Get-CandidateProcesses)
    if ($Remaining.Count -ne 0) {
        throw "Candidate acceptance ended with $($Remaining.Count) Emulator process(es) still running."
    }

    $Record = [ordered]@{
        schema = "innaware-pms-emulator-windows-field-acceptance/v1"
        source_sha = $SourceSha.ToLowerInvariant()
        executable_sha256 = $ActualExeSha256
        disposable_data_dirs = $true
        telemetry_disabled = $true
        update_checks_disabled = $true
        production_endpoints_used = $false
        server5_used = $false
        child_processes_remaining = $false
        native_gui = $Native
        browser = $Browser
    }

    $OutputPath = [System.IO.Path]::GetFullPath($Output)
    $OutputParent = Split-Path -Parent $OutputPath
    if ($OutputParent) {
        New-Item -ItemType Directory -Force -Path $OutputParent | Out-Null
    }
    $Record | ConvertTo-Json -Depth 8 | Set-Content -Path $OutputPath -Encoding UTF8

    Write-Host ""
    Write-Host "Windows field candidate acceptance PASS" -ForegroundColor Green
    Write-Host "Source SHA : $SourceSha"
    Write-Host "EXE SHA-256: $ActualExeSha256"
    Write-Host "Evidence    : $OutputPath"
}
finally {
    Stop-CandidateProcessTree -RootPid 0
    if ($null -eq $OriginalDataDir) {
        Remove-Item Env:INNAWARE_PMS_DATA_DIR -ErrorAction SilentlyContinue
    }
    else {
        $env:INNAWARE_PMS_DATA_DIR = $OriginalDataDir
    }
    foreach ($Root in $TempRoots) {
        Remove-Item -Recurse -Force $Root -ErrorAction SilentlyContinue
    }
}

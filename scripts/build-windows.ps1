param(
    [string]$Python = "py",
    [string]$OutputDir = "dist-windows"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Venv = Join-Path $RepoRoot ".venv-winbuild"
if (-not (Test-Path $Venv)) {
    if ($Python -eq "py") {
        & py -3 -m venv $Venv
    }
    else {
        & $Python -m venv $Venv
    }
    if ($LASTEXITCODE -ne 0) { throw "Unable to create Windows build virtual environment." }
}

$Py = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Py)) { throw "Python virtual environment is incomplete: $Py" }

& $Py -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
& $Py -m pip install -e . pytest pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Build dependencies failed to install" }

& $Py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Regression tests failed; refusing to package Windows executable." }

if (Test-Path $OutputDir) {
    Remove-Item -Recurse -Force $OutputDir
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

& $Py -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name InnAware-PMS-Emulator `
    --collect-all innaware_pms_emulator `
    --collect-all uvicorn `
    --collect-all fastapi `
    --collect-all serial_asyncio `
    --distpath $OutputDir `
    src\innaware_pms_emulator\windows_launcher.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

$Exe = Join-Path $OutputDir "InnAware-PMS-Emulator.exe"
if (-not (Test-Path $Exe)) {
    throw "Windows executable was not produced: $Exe"
}

$Hash = Get-FileHash -Algorithm SHA256 $Exe
$HashLine = "$($Hash.Hash.ToLower())  InnAware-PMS-Emulator.exe"
Set-Content -Path (Join-Path $OutputDir "SHA256SUMS.txt") -Value $HashLine -Encoding ascii

$Readme = @"
InnAware PMS Emulator - Windows Field Build

Run:
    InnAware-PMS-Emulator.exe

The emulator starts a local web service on http://127.0.0.1:8080 and opens the operator console in the default browser.
Property/interface state is stored under %LOCALAPPDATA%\InnAware\PMS Emulator unless INNAWARE_PMS_DATA_DIR is set.

Useful options:
    InnAware-PMS-Emulator.exe --no-browser
    InnAware-PMS-Emulator.exe --port 8081
    InnAware-PMS-Emulator.exe --host 0.0.0.0

For normal field use, keep the HTTP service bound to 127.0.0.1. Binding to 0.0.0.0 exposes the web UI/API to the local network and should only be done intentionally.

Serial ports are discovered in the operator console and use Windows COM names such as COM1, COM3 or COM7.
This software is a test/emulation instrument. Do not connect it to a production PMS or billing endpoint unless test traffic is explicitly intended.
"@
Set-Content -Path (Join-Path $OutputDir "README-WINDOWS.txt") -Value $Readme -Encoding utf8

$Zip = Join-Path $RepoRoot "InnAware-PMS-Emulator-Windows.zip"
if (Test-Path $Zip) { Remove-Item -Force $Zip }
Compress-Archive -Path (Join-Path $OutputDir "*") -DestinationPath $Zip

$SourceZip = Join-Path $RepoRoot "InnAware-PMS-Emulator-Source.zip"
if (Test-Path $SourceZip) { Remove-Item -Force $SourceZip }
& git archive --format=zip --output=$SourceZip HEAD
if ($LASTEXITCODE -ne 0) { throw "Unable to create source archive with git archive" }

Write-Host ""
Write-Host "Build complete:" -ForegroundColor Green
Write-Host "  EXE: $Exe"
Write-Host "  Windows ZIP: $Zip"
Write-Host "  Source ZIP: $SourceZip"
Write-Host "  SHA256: $($Hash.Hash.ToLower())"

param(
    [string]$Python = "py",
    [string]$OutputDir = "dist-windows"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Venv = Join-Path $RepoRoot ".venv-winbuild"
if (-not (Test-Path $Venv)) {
    & $Python -3 -m venv $Venv
}

$Py = Join-Path $Venv "Scripts\python.exe"
$Pip = Join-Path $Venv "Scripts\pip.exe"

& $Py -m pip install --upgrade pip
& $Pip install -e . pytest pyinstaller
& $Py -m pytest -q

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

Useful options:
    InnAware-PMS-Emulator.exe --no-browser
    InnAware-PMS-Emulator.exe --port 8081
    InnAware-PMS-Emulator.exe --host 0.0.0.0

For normal field use, keep the HTTP service bound to 127.0.0.1. Binding to 0.0.0.0 exposes the web UI/API to the local network and should only be done intentionally.

Serial ports use Windows COM names such as COM1, COM3, COM7, etc.
"@
Set-Content -Path (Join-Path $OutputDir "README-WINDOWS.txt") -Value $Readme -Encoding utf8

$Zip = Join-Path $RepoRoot "InnAware-PMS-Emulator-Windows.zip"
if (Test-Path $Zip) {
    Remove-Item -Force $Zip
}
Compress-Archive -Path (Join-Path $OutputDir "*") -DestinationPath $Zip

Write-Host ""
Write-Host "Build complete:" -ForegroundColor Green
Write-Host "  EXE: $Exe"
Write-Host "  ZIP: $Zip"
Write-Host "  SHA256: $($Hash.Hash.ToLower())"

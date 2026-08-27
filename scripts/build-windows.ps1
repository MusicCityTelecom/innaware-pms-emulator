param(
    [string]$Python = "py",
    [string]$OutputDir = "dist-windows",
    [switch]$SkipInstaller
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
& $Py -m pip install -e ".[windows]" pytest pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Build dependencies failed to install" }

$Version = (& $Py -c "import innaware_pms_emulator; print(innaware_pms_emulator.__version__)").Trim()
if (-not $Version) { throw "Unable to determine application version" }
Write-Host "Building InnAware PMS Emulator $Version" -ForegroundColor Cyan

& $Py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Regression tests failed; refusing to package Windows executable." }

if (Test-Path $OutputDir) {
    Remove-Item -Recurse -Force $OutputDir
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$VersionParts = $Version.Split('.')
while ($VersionParts.Count -lt 4) { $VersionParts += '0' }
$VersionTuple = ($VersionParts[0..3] -join ', ')
$VersionFile = Join-Path $env:TEMP "innaware-pms-version-info.txt"
@"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($VersionTuple),
    prodvers=($VersionTuple),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'InnAware'),
         StringStruct(u'FileDescription', u'InnAware PMS Emulator'),
         StringStruct(u'FileVersion', u'$Version'),
         StringStruct(u'InternalName', u'InnAware-PMS-Emulator'),
         StringStruct(u'LegalCopyright', u'Copyright InnAware contributors'),
         StringStruct(u'OriginalFilename', u'InnAware-PMS-Emulator.exe'),
         StringStruct(u'ProductName', u'InnAware PMS Emulator'),
         StringStruct(u'ProductVersion', u'$Version')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"@ | Set-Content -Path $VersionFile -Encoding utf8

& $Py -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name InnAware-PMS-Emulator `
    --version-file $VersionFile `
    --collect-all innaware_pms_emulator `
    --collect-all uvicorn `
    --collect-all fastapi `
    --collect-all serial_asyncio `
    --collect-all webview `
    --hidden-import webview.platforms.edgechromium `
    --distpath $OutputDir `
    src\innaware_pms_emulator\windows_launcher.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

$Exe = Join-Path $OutputDir "InnAware-PMS-Emulator.exe"
if (-not (Test-Path $Exe)) {
    throw "Windows executable was not produced: $Exe"
}

$Readme = @"
InnAware PMS Emulator $Version - Windows Field Build

QUICK START
===========
1. Run InnAware-PMS-Emulator.exe.
2. The local engine starts automatically and opens in a native Windows application window.
3. Create or seed a property.
4. Configure a PMS interface and, independently, a call-accounting interface.
5. Choose TCP Server, TCP Client, or an available Windows COM port.
6. Start testing and use Live Wire Capture to inspect traffic.

DATA
====
Persistent state and logs are stored under:
  %LOCALAPPDATA%\InnAware\PMS Emulator

The management API binds to 127.0.0.1:8080 by default. PMS/call-accounting interfaces may bind to LAN addresses as required by the test.

SUPPORT
=======
A privacy-aware support bundle is available from:
  http://127.0.0.1:8080/api/v1/support-bundle

Full guest/property state is excluded by default.

COMMAND-LINE OPTIONS
====================
  InnAware-PMS-Emulator.exe --port 8081
  InnAware-PMS-Emulator.exe --browser
  InnAware-PMS-Emulator.exe --no-browser
  InnAware-PMS-Emulator.exe --host 0.0.0.0

Normal field use should keep the management interface on 127.0.0.1.

This software is a test/emulation instrument. Do not connect it to a production PMS or billing endpoint unless test traffic is explicitly intended and authorized.
"@
Set-Content -Path (Join-Path $OutputDir "README-WINDOWS.txt") -Value $Readme -Encoding utf8

$HashLines = @()
$ExeHash = Get-FileHash -Algorithm SHA256 $Exe
$HashLines += "$($ExeHash.Hash.ToLower())  InnAware-PMS-Emulator.exe"
Set-Content -Path (Join-Path $OutputDir "SHA256SUMS.txt") -Value $HashLines -Encoding ascii

$Installer = $null
if (-not $SkipInstaller) {
    $IsccCandidates = @(
        "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    ) | Where-Object { $_ -and (Test-Path $_) }

    if ($IsccCandidates.Count -gt 0) {
        $Iscc = $IsccCandidates[0]
        $Iss = Join-Path $RepoRoot "packaging\windows\InnAware-PMS-Emulator.iss"
        & $Iscc "/DAppVersion=$Version" "/DSourceDir=$((Resolve-Path $OutputDir).Path)" $Iss
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup build failed" }
        $Installer = Join-Path $OutputDir "InnAware-PMS-Emulator-Setup.exe"
        if (-not (Test-Path $Installer)) { throw "Installer build completed but Setup.exe was not found" }
        $InstallerHash = Get-FileHash -Algorithm SHA256 $Installer
        $HashLines += "$($InstallerHash.Hash.ToLower())  InnAware-PMS-Emulator-Setup.exe"
        Set-Content -Path (Join-Path $OutputDir "SHA256SUMS.txt") -Value $HashLines -Encoding ascii
    }
    else {
        Write-Warning "Inno Setup 6 was not found. Portable EXE/ZIP will be built; install Inno Setup 6 to also produce Setup.exe."
    }
}

$Zip = Join-Path $RepoRoot "InnAware-PMS-Emulator-Windows-$Version.zip"
if (Test-Path $Zip) { Remove-Item -Force $Zip }
$PortableFiles = @(
    $Exe,
    (Join-Path $OutputDir "README-WINDOWS.txt"),
    (Join-Path $OutputDir "SHA256SUMS.txt")
)
Compress-Archive -Path $PortableFiles -DestinationPath $Zip

$SourceZip = Join-Path $RepoRoot "InnAware-PMS-Emulator-Source-$Version.zip"
if (Test-Path $SourceZip) { Remove-Item -Force $SourceZip }
& git archive --format=zip --output=$SourceZip HEAD
if ($LASTEXITCODE -ne 0) { throw "Unable to create source archive with git archive" }

$ZipHash = Get-FileHash -Algorithm SHA256 $Zip
$SourceHash = Get-FileHash -Algorithm SHA256 $SourceZip
$ReleaseSums = @(
    "$($ExeHash.Hash.ToLower())  InnAware-PMS-Emulator.exe",
    "$($ZipHash.Hash.ToLower())  $(Split-Path -Leaf $Zip)",
    "$($SourceHash.Hash.ToLower())  $(Split-Path -Leaf $SourceZip)"
)
if ($Installer) {
    $ReleaseSums += "$($InstallerHash.Hash.ToLower())  InnAware-PMS-Emulator-Setup.exe"
}
Set-Content -Path (Join-Path $RepoRoot "SHA256SUMS-WINDOWS-$Version.txt") -Value $ReleaseSums -Encoding ascii

Write-Host ""
Write-Host "Build complete:" -ForegroundColor Green
Write-Host "  Version:      $Version"
Write-Host "  Portable EXE: $Exe"
if ($Installer) { Write-Host "  Installer:    $Installer" }
Write-Host "  Windows ZIP:  $Zip"
Write-Host "  Source ZIP:   $SourceZip"
Write-Host "  Checksums:    $(Join-Path $RepoRoot "SHA256SUMS-WINDOWS-$Version.txt")"

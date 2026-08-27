param(
    [string]$Python = "py",
    [string]$OutputDir = "dist-windows",
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Author = "Tommy Heggie"
$ProductName = "InnAware PMS Emulator"

$OutputPath = if ([System.IO.Path]::IsPathRooted($OutputDir)) {
    [System.IO.Path]::GetFullPath($OutputDir)
}
else {
    [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $OutputDir))
}
$PreviousExe = Join-Path $OutputPath "InnAware-PMS-Emulator.exe"
$TaskKill = Join-Path $env:SystemRoot "System32\taskkill.exe"

function Get-OutputExeProcesses {
    param([string]$ExePath)

    if (-not $ExePath) { return @() }
    $Expected = [System.IO.Path]::GetFullPath($ExePath)
    try {
        return @(Get-CimInstance Win32_Process -Filter "Name='InnAware-PMS-Emulator.exe'" -ErrorAction SilentlyContinue |
            Where-Object {
                $_.ExecutablePath -and
                ([System.IO.Path]::GetFullPath($_.ExecutablePath) -ieq $Expected)
            })
    }
    catch {
        return @()
    }
}

function Stop-OutputExeProcesses {
    param([string]$ExePath)

    $Matches = @(Get-OutputExeProcesses -ExePath $ExePath)
    if ($Matches.Count -eq 0) { return }

    Write-Host "Stopping prior InnAware PMS Emulator process tree(s) from build output..." -ForegroundColor Yellow
    foreach ($Item in $Matches) {
        Write-Host "  PID $($Item.ProcessId): $($Item.ExecutablePath)" -ForegroundColor DarkGray
        if (Test-Path $TaskKill) {
            & $TaskKill /PID $Item.ProcessId /T /F 2>$null | Out-Null
        }
        else {
            Stop-Process -Id $Item.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }

    for ($i = 0; $i -lt 50; $i++) {
        if (@(Get-OutputExeProcesses -ExePath $ExePath).Count -eq 0) { return }
        Start-Sleep -Milliseconds 100
    }
}

function Remove-BuildOutputDirectory {
    param([string]$Path, [string]$ExePath)

    if (-not (Test-Path -LiteralPath $Path)) { return }

    Stop-OutputExeProcesses -ExePath $ExePath

    $LastError = $null
    for ($Attempt = 1; $Attempt -le 40; $Attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return
        }
        catch {
            $LastError = $_
            if ($Attempt -eq 1) {
                Write-Host "Build output is temporarily locked; waiting for Windows to release file handles..." -ForegroundColor Yellow
            }
            Start-Sleep -Milliseconds 250
            Stop-OutputExeProcesses -ExePath $ExePath
        }
    }

    $Remaining = @(Get-OutputExeProcesses -ExePath $ExePath)
    if ($Remaining.Count -gt 0) {
        $Pids = @($Remaining | ForEach-Object { $_.ProcessId }) -join ", "
        throw "Unable to clean '$Path'. InnAware-PMS-Emulator.exe is still running from that directory (PID(s): $Pids). Close the application and retry. Last error: $($LastError.Exception.Message)"
    }

    throw "Unable to clean '$Path' after 10 seconds. Windows still has a file handle open (often antivirus/indexing immediately after a new EXE is run). Retry once the handle is released. Last error: $($LastError.Exception.Message)"
}

function Find-InnoSetupCompiler {
    $Candidates = @()

    try {
        $Command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        if ($Command -and $Command.Source) {
            $Candidates += $Command.Source
        }
    }
    catch {}

    $ProgramFilesX86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    $ProgramFiles64 = [Environment]::GetEnvironmentVariable("ProgramFiles")
    $LocalAppData = [Environment]::GetEnvironmentVariable("LOCALAPPDATA")

    if ($ProgramFilesX86) {
        $Candidates += (Join-Path $ProgramFilesX86 "Inno Setup 6\ISCC.exe")
    }
    if ($ProgramFiles64) {
        $Candidates += (Join-Path $ProgramFiles64 "Inno Setup 6\ISCC.exe")
    }
    if ($LocalAppData) {
        $Candidates += (Join-Path $LocalAppData "Programs\Inno Setup 6\ISCC.exe")
    }

    $Existing = @(
        $Candidates |
            Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
            ForEach-Object { [System.IO.Path]::GetFullPath($_) } |
            Select-Object -Unique
    )

    if ($Existing.Count -gt 0) {
        return $Existing[0]
    }
    return $null
}

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
Write-Host "Building $ProductName $Version" -ForegroundColor Cyan
Write-Host "Author: $Author" -ForegroundColor DarkGray

& $Py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Regression tests failed; refusing to package Windows executable." }

Remove-BuildOutputDirectory -Path $OutputPath -ExePath $PreviousExe
New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null

$VersionParts = @($Version.Split('.'))
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
         StringStruct(u'LegalCopyright', u'Copyright (c) 2026 Tommy Heggie'),
         StringStruct(u'Comments', u'Created and maintained by Tommy Heggie'),
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
    --distpath $OutputPath `
    src\innaware_pms_emulator\windows_launcher.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

$Exe = Join-Path $OutputPath "InnAware-PMS-Emulator.exe"
if (-not (Test-Path $Exe)) { throw "Windows executable was not produced: $Exe" }

$SmokeScript = Join-Path $PSScriptRoot "smoke-windows.ps1"
& $SmokeScript -Exe $Exe

for ($i = 0; $i -lt 20; $i++) {
    if (@(Get-OutputExeProcesses -ExePath $Exe).Count -eq 0) { break }
    Start-Sleep -Milliseconds 100
}

$Readme = @"
InnAware PMS Emulator $Version - Windows Field Build
Author: Tommy Heggie

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
Privacy-aware support bundle:
  http://127.0.0.1:8080/api/v1/support-bundle

Capture export:
  http://127.0.0.1:8080/api/v1/interfaces/INTERFACE_NAME/captures/export?format=csv

Full guest/property state is excluded from support bundles by default.

COMMAND-LINE OPTIONS
====================
  InnAware-PMS-Emulator.exe --port 8081
  InnAware-PMS-Emulator.exe --browser
  InnAware-PMS-Emulator.exe --no-browser
  InnAware-PMS-Emulator.exe --host 0.0.0.0

Normal field use should keep the management interface on 127.0.0.1.

This software is a test/emulation instrument. Do not connect it to a production PMS or billing endpoint unless test traffic is explicitly intended and authorized.

Copyright (c) 2026 Tommy Heggie.
"@
Set-Content -Path (Join-Path $OutputPath "README-WINDOWS.txt") -Value $Readme -Encoding utf8

$ExeHash = Get-FileHash -Algorithm SHA256 $Exe
$HashLines = @("$($ExeHash.Hash.ToLower())  InnAware-PMS-Emulator.exe")
Set-Content -Path (Join-Path $OutputPath "SHA256SUMS.txt") -Value $HashLines -Encoding ascii

$Installer = $null
$InstallerHash = $null
if (-not $SkipInstaller) {
    $Iscc = Find-InnoSetupCompiler
    if ($Iscc) {
        Write-Host "Using Inno Setup compiler: $Iscc" -ForegroundColor DarkGray
        $Iss = Join-Path $RepoRoot "packaging\windows\InnAware-PMS-Emulator.iss"
        & $Iscc "/DAppVersion=$Version" "/DSourceDir=$OutputPath" $Iss
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup build failed" }
        $Installer = Join-Path $OutputPath "InnAware-PMS-Emulator-Setup.exe"
        if (-not (Test-Path $Installer)) { throw "Installer build completed but Setup.exe was not found" }
        $InstallerHash = Get-FileHash -Algorithm SHA256 $Installer
        $HashLines += "$($InstallerHash.Hash.ToLower())  InnAware-PMS-Emulator-Setup.exe"
        Set-Content -Path (Join-Path $OutputPath "SHA256SUMS.txt") -Value $HashLines -Encoding ascii
    }
    else {
        Write-Warning "Inno Setup 6 was not found. Portable EXE/ZIP will be built; install Inno Setup 6 to also produce Setup.exe. Checked PATH, Program Files, Program Files (x86), and LOCALAPPDATA\Programs."
    }
}

$Zip = Join-Path $RepoRoot "InnAware-PMS-Emulator-Windows-$Version.zip"
if (Test-Path $Zip) { Remove-Item -Force $Zip }
$PortableFiles = @(
    $Exe,
    (Join-Path $OutputPath "README-WINDOWS.txt"),
    (Join-Path $OutputPath "SHA256SUMS.txt")
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
if ($InstallerHash) { $ReleaseSums += "$($InstallerHash.Hash.ToLower())  InnAware-PMS-Emulator-Setup.exe" }
$ReleaseChecksumFile = Join-Path $RepoRoot "SHA256SUMS-WINDOWS-$Version.txt"
Set-Content -Path $ReleaseChecksumFile -Value $ReleaseSums -Encoding ascii

Write-Host ""
Write-Host "Build complete:" -ForegroundColor Green
Write-Host "  Product:      $ProductName"
Write-Host "  Author:       $Author"
Write-Host "  Version:      $Version"
Write-Host "  Portable EXE: $Exe"
if ($Installer) { Write-Host "  Installer:    $Installer" }
Write-Host "  Windows ZIP:  $Zip"
Write-Host "  Source ZIP:   $SourceZip"
Write-Host "  Checksums:    $ReleaseChecksumFile"

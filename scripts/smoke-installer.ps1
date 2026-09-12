param([string]$OutputDir = 'dist-windows')
$ErrorActionPreference = 'Stop'
# This test exercises installer registration; run only on disposable CI machines.
if ($env:GITHUB_ACTIONS -ne 'true') { throw 'Installer smoke requires a disposable GitHub Actions Windows runner.' }
$OutputPath = (Resolve-Path $OutputDir).Path
$Setup = Join-Path $OutputPath 'InnAware-PMS-Emulator-Setup.exe'
$TestRoot = Join-Path $env:RUNNER_TEMP ('innaware-installer-' + [guid]::NewGuid().ToString('N'))
$InstallDir = Join-Path $TestRoot 'app'
New-Item -ItemType Directory -Path $TestRoot | Out-Null
$InstallArguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS', "/DIR=`"$InstallDir`"", "/LOG=`"$TestRoot\install.log`"")
foreach ($Pass in @(1, 2)) {
    $InstallerProcess = Start-Process -FilePath $Setup -ArgumentList $InstallArguments -WindowStyle Hidden -PassThru
    if (-not $InstallerProcess.WaitForExit(120000)) { $InstallerProcess.Kill(); throw 'Installer timed out.' }
    if ($InstallerProcess.ExitCode -ne 0) { throw "Installer failed: $($InstallerProcess.ExitCode)" }
    foreach ($Name in @('InnAware-PMS-Emulator.exe', 'build-info.json', 'README-WINDOWS.txt', 'PRIVACY-TELEMETRY.md', 'SHA256SUMS.txt')) {
        $Installed = Join-Path $InstallDir $Name
        if (-not (Test-Path $Installed)) { throw "Installer omitted $Name" }
        if ((Get-FileHash $Installed).Hash -ne (Get-FileHash (Join-Path $OutputPath $Name)).Hash) { throw "Installed $Name differs from release asset." }
    }
    if ($Pass -eq 1) { 'Synthetic user-added file' | Set-Content (Join-Path $InstallDir 'user-file.txt') }
    elseif (-not (Test-Path (Join-Path $InstallDir 'user-file.txt'))) { throw 'Reinstall removed a user-added file.' }
}
& (Join-Path $PSScriptRoot 'smoke-windows.ps1') -Exe (Join-Path $InstallDir 'InnAware-PMS-Emulator.exe') -Port 18083
$Uninstaller = Join-Path $InstallDir 'unins000.exe'
$UninstallProcess = Start-Process -FilePath $Uninstaller -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -WindowStyle Hidden -PassThru
if (-not $UninstallProcess.WaitForExit(120000)) { $UninstallProcess.Kill(); throw 'Uninstaller timed out.' }
if ($UninstallProcess.ExitCode -ne 0) { throw "Uninstaller failed: $($UninstallProcess.ExitCode)" }
if (Test-Path (Join-Path $InstallDir 'InnAware-PMS-Emulator.exe')) { throw 'Uninstall left the executable installed.' }
if (-not (Test-Path (Join-Path $InstallDir 'user-file.txt'))) { throw 'Uninstall deleted a user-added file.' }
Write-Host 'Installer, reinstall, installed application, and uninstall preservation PASS'

#ifndef AppVersion
  #define AppVersion "0.3.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist-windows"
#endif

#define AppName "InnAware PMS Emulator"
#define AppExeName "InnAware-PMS-Emulator.exe"
#define AppPublisher "Tommy Heggie"
#define AppURL "https://github.com/MusicCityTelecom/innaware-pms-emulator"

[Setup]
AppId={{A54BD30A-BC7D-46AB-AE64-054A79D68EC2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={localappdata}\Programs\InnAware PMS Emulator
DefaultGroupName=InnAware PMS Emulator
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#SourceDir}
OutputBaseFilename=InnAware-PMS-Emulator-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExeName}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoCopyright=Copyright (c) 2026 Tommy Heggie
SetupLogging=yes
CloseApplications=force
CloseApplicationsFilter={#AppExeName}
RestartApplications=no

[Files]
Source: "{#SourceDir}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\README-WINDOWS.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\SHA256SUMS.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\InnAware PMS Emulator"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\InnAware PMS Emulator"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch InnAware PMS Emulator"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  { PyInstaller one-file mode may leave a launcher and child process using the
    installed EXE. Restart Manager does not consistently close that process
    tree, so terminate only this product image before replacing the file. }
  Exec(
    ExpandConstant('{sys}\taskkill.exe'),
    '/F /T /IM "{#AppExeName}"',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
  Sleep(500);
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;

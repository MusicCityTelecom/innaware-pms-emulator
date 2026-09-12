#ifndef AppVersion
  #error AppVersion must be supplied by the canonical Windows build script
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist-windows"
#endif

#define AppName "InnAware PMS Emulator"
#define AppExeName "InnAware-PMS-Emulator.exe"
#define AppPublisher "Tommy Heggie"
#define AppURL "https://github.com/MusicCityTelecom/innaware-pms-emulator"
#define SupportURL "https://support.innawareucp.com"

[Setup]
AppId={{A54BD30A-BC7D-46AB-AE64-054A79D68EC2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#SupportURL}
AppUpdatesURL={#AppURL}/releases
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
Source: "{#SourceDir}\PRIVACY-TELEMETRY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\SHA256SUMS.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\build-info.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\InnAware PMS Emulator"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autoprograms}\InnAware PMS Emulator (Browser)"; Filename: "{app}\{#AppExeName}"; Parameters: "--browser"; WorkingDir: "{app}"
Name: "{autodesktop}\InnAware PMS Emulator"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch InnAware PMS Emulator"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeUninstall(): Boolean;
begin
  Result := True;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;

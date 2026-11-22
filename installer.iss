#define AppName "Epicerie Enterprise"
#define AppVersion "97.0-buildkit"
#define AppExe "EpicerieEnterprise.exe"
[Setup]
AppId={{A1ED6C47-83A2-44EA-B69E-4F9B2A5E5C37}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\Epicerie Enterprise
DefaultGroupName={#AppName}
OutputDir=installer_output
OutputBaseFilename=EpicerieEnterprise_Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}
[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\EpicerieRecovery.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "WINDOWS_ACCEPTANCE_AR.md"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{group}\Acceptance Checklist"; Filename: "{app}\WINDOWS_ACCEPTANCE_AR.md"
Name: "{group}\Data Recovery"; Filename: "{app}\EpicerieRecovery.exe"
[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; GroupDescription: "Additional icons:"
[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch Epicerie Enterprise"; Flags: nowait postinstall skipifsilent

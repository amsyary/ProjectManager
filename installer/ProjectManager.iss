; Inno Setup script for Project Manager.
; Build the folder version first:  set PM_ONEDIR=1 && py -m PyInstaller --clean --noconfirm ProjectManager.spec
; Then:  iscc /DAppVersion=1.2.3 installer\ProjectManager.iss   (output: installer\Output\)
;
; Installs per user (no admin prompt) into %LOCALAPPDATA%\Programs, because the app keeps its
; data\ and config\ folders next to ProjectManager.exe and needs to write there.

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

#define AppName "Project Manager"
#define AppExe "ProjectManager.exe"
#define AppPublisher "Amsyari"
#define AppURL "https://github.com/amsyary/ProjectManager"

[Setup]
AppId={{7E3C1E52-4B8A-4C1D-9C55-2E6F0B9A31D7}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=Output
OutputBaseFilename=ProjectManager-Setup-{#AppVersion}-x64
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
LicenseFile=..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The app's own files only: the user's data\ and config\ folders are never shipped or overwritten
Source: "..\dist\ProjectManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

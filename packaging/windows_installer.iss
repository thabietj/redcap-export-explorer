#define MyAppName "REDCap Export Explorer"
#define MyAppVersion "0.3.1"
#define MyAppPublisher "REDCap Export Explorer"
#define MyAppExeName "REDCapExportExplorer.exe"

[Setup]
AppId={{E1150CBA-031F-49ED-AE22-E102EDCC03D4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\REDCap Export Explorer
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=REDCap-Export-Explorer-0.3.1-Windows-x64-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

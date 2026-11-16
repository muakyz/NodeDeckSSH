; Optional Inno Setup installer. Run build_windows.bat first.
#define AppName "NodeDeck SSH"
#define AppVersion "0.10.1"
#define AppExe "NodeDeckSSH.exe"
[Setup]
AppId={{B9B427E1-3B15-4C71-ACBD-D5802E343A9D}
AppName={#AppName}
AppVersion={#AppVersion}
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\NodeDeck SSH
DefaultGroupName=NodeDeck SSH
OutputDir=installer
OutputBaseFilename=NodeDeckSSH-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
SetupIconFile=assets\nodedeck.ico
UninstallDisplayIcon={app}\{#AppExe}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "install_keepass_bridge.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "keepass-bridge\NodeDeckBridge.cs"; DestDir: "{app}\keepass-bridge"; Flags: ignoreversion
[Icons]
Name: "{group}\NodeDeck SSH"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\NodeDeck SSH"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch NodeDeck SSH"; Flags: nowait postinstall skipifsilent

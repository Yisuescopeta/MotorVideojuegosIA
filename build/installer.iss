; Inno Setup Script para OpenGame
; Genera: OpenGame-{version}-Setup.exe
;
; Requisito: Inno Setup 6 (https://jrsoftware.org/isinfo.php)
; Compilar: ISCC.exe build\installer.iss

#ifndef AppVersion
  #define AppVersion "2026.06"
#endif

[Setup]
AppId={{B8F2C3A1-4D5E-6F78-9A0B-C1D2E3F4A5B6}
AppName=OpenGame
AppVersion={#AppVersion}
AppVerName=OpenGame {#AppVersion}
AppPublisher=Yisuescopeta
AppPublisherURL=https://github.com/Yisuescopeta/OpenGame
DefaultDirName={autopf}\OpenGame
DefaultGroupName=OpenGame
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=OpenGame-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayName=OpenGame {#AppVersion}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Incluir toda la carpeta generada por PyInstaller
Source: "..\dist\OpenGame\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\OpenGame"; Filename: "{app}\OpenGame.exe"; WorkingDir: "{app}"
Name: "{group}\Desinstalar OpenGame"; Filename: "{uninstallexe}"
Name: "{autodesktop}\OpenGame"; Filename: "{app}\OpenGame.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\OpenGame.exe"; Description: "Ejecutar OpenGame"; Flags: nowait postinstall skipifsilent

; Inno Setup Script para MotorVideojuegosIA
; Genera: MotorVideojuegosIA-{version}-Setup.exe
;
; Requisito: Inno Setup 6 (https://jrsoftware.org/isinfo.php)
; Compilar: ISCC.exe build\installer.iss

#ifndef AppVersion
  #define AppVersion "2026.03"
#endif

[Setup]
AppId={{B8F2C3A1-4D5E-6F78-9A0B-C1D2E3F4A5B6}
AppName=MotorVideojuegosIA
AppVersion={#AppVersion}
AppVerName=MotorVideojuegosIA {#AppVersion}
AppPublisher=Yisuescopeta
AppPublisherURL=https://github.com/Yisuescopeta/MotorVideojuegosIA
DefaultDirName={autopf}\MotorVideojuegosIA
DefaultGroupName=MotorVideojuegosIA
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=MotorVideojuegosIA-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayName=MotorVideojuegosIA {#AppVersion}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Incluir toda la carpeta generada por PyInstaller
Source: "..\dist\MotorVideojuegosIA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MotorVideojuegosIA"; Filename: "{app}\MotorVideojuegosIA.exe"; WorkingDir: "{app}"
Name: "{group}\Desinstalar MotorVideojuegosIA"; Filename: "{uninstallexe}"
Name: "{autodesktop}\MotorVideojuegosIA"; Filename: "{app}\MotorVideojuegosIA.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\MotorVideojuegosIA.exe"; Description: "Ejecutar MotorVideojuegosIA"; Flags: nowait postinstall skipifsilent

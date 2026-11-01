#ifndef AppVersion
  #error AppVersion is required
#endif
#define AppName "WalkSim Mobility"

[Setup]
AppId={{5747A1D2-BB21-43D9-A66D-B773F41F4E2A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Héctor Alonso Benítez García
AppPublisherURL=https://github.com/VanLinux/walksim-mobility
AppSupportURL=mailto:prof.benitezgh@gmail.com
DefaultDirName={localappdata}\Programs\WalkSim Mobility
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\..\dist\installer
OutputBaseFilename=WalkSim-Mobility-{#AppVersion}-Windows-x64-Setup
SetupIconFile=..\..\build\windows\WalkSim.ico
UninstallDisplayIcon={app}\WalkSim.exe
LicenseFile=..\..\LICENSE
InfoAfterFile=LEEME.txt
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayName={#AppName} (incluye SUMO)

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "..\..\dist\WalkSim\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\WalkSim Mobility"; Filename: "{app}\WalkSim.exe"; WorkingDir: "{userdocs}"
Name: "{autodesktop}\WalkSim Mobility"; Filename: "{app}\WalkSim.exe"; WorkingDir: "{userdocs}"
Name: "{group}\Desinstalar WalkSim Mobility"; Filename: "{uninstallexe}"
Name: "{group}\Ejemplos y plantillas"; Filename: "{app}\examples"

[Run]
Filename: "{app}\WalkSim.exe"; Description: "Abrir WalkSim Mobility"; Flags: nowait postinstall skipifsilent



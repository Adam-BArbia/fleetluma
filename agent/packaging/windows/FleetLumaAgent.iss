; FL-43 unsigned Windows installer candidate. NOT A PRODUCTION RELEASE.
; Source binaries must already exist from the reviewed FL-41 PyInstaller build.
#define MyAppName "FleetLuma Agent"
#define MyAppVersion "0.1.0-rc.1"

[Setup]
AppId={{2CD09B45-0C74-4B8A-BC81-72A9D899D783}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=FleetLuma
DefaultDirName={autopf}\FleetLuma
DefaultGroupName=FleetLuma
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputDir=..\..\..\dist\windows-installer
OutputBaseFilename=FleetLuma-Agent-Windows-UNSIGNED-CANDIDATE
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayName=FleetLuma Agent

[Files]
Source: "..\..\..\dist\FleetLumaAgent\*"; DestDir: "{app}\Agent"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\..\dist\FleetLumaSetup.exe"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{commonappdata}\FleetLuma"
Name: "{commonappdata}\FleetLuma\private"

[Icons]
Name: "{group}\FleetLuma Agent Setup"; Filename: "{app}\FleetLumaSetup.exe"
Name: "{autodesktop}\FleetLuma Agent Setup"; Filename: "{app}\FleetLumaSetup.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\FleetLumaSetup.exe"; Description: "Configure FleetLuma Agent"; Flags: postinstall skipifsilent nowait

[UninstallDelete]
; Removing the agent removes the locally stored service credential.
Type: filesandordirs; Name: "{commonappdata}\FleetLuma"

[Code]
procedure ScCommand(const Arguments: String);
var
  ExitCode: Integer;
begin
  if not Exec(ExpandConstant('{sys}\sc.exe'), Arguments, '',
              SW_HIDE, ewWaitUntilTerminated, ExitCode) then
    RaiseException('Windows Service Control Manager could not be invoked');
  if ExitCode <> 0 then
    RaiseException('FleetLuma service configuration failed (' + IntToStr(ExitCode) + ')');
end;

procedure ApplyPrivateAcl();
var
  ExitCode: Integer;
  Target, Arguments: String;
begin
  Target := ExpandConstant('{commonappdata}\FleetLuma');
  // SID-based ACLs work on localized Windows installations.
  Arguments := '"' + Target + '" /inheritance:r /grant:r ' +
    '"*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" /T';
  if not Exec(ExpandConstant('{sys}\icacls.exe'), Arguments, '',
              SW_HIDE, ewWaitUntilTerminated, ExitCode) then
    RaiseException('Could not protect FleetLuma service credentials');
  if ExitCode <> 0 then
    RaiseException('FleetLuma private service ACL initialization failed');
end;

function HasExistingService(): Boolean;
var
  ExitCode: Integer;
begin
  Result := Exec(ExpandConstant('{sys}\sc.exe'), 'query FleetLumaAgent', '',
                 SW_HIDE, ewWaitUntilTerminated, ExitCode) and (ExitCode = 0);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ExitCode, I: Integer;
  BinaryPath: String;
begin
  if CurStep = ssInstall then
  begin
    if HasExistingService() then
    begin
      Exec(ExpandConstant('{sys}\sc.exe'), 'stop FleetLumaAgent', '',
           SW_HIDE, ewWaitUntilTerminated, ExitCode);
      for I := 1 to 20 do
      begin
        Sleep(500);
        // Windows may take several seconds to stop a monitored service.
      end;
    end;
  end;
  if CurStep = ssPostInstall then
  begin
    ApplyPrivateAcl();
    if not HasExistingService() then
    begin
      BinaryPath := ExpandConstant('{app}\Agent\FleetLumaAgent.exe');
      ScCommand('create FleetLumaAgent binPath= "' + BinaryPath +
                '" start= auto obj= LocalSystem DisplayName= "FleetLuma Monitoring Agent"');
    end;
    // Enable the dedicated service SID used by the protected pipe ACL.
    ScCommand('sidtype FleetLumaAgent unrestricted');
    ScCommand('config FleetLumaAgent start= auto');
    ScCommand('start FleetLumaAgent');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ExitCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    if HasExistingService() then
    begin
      Exec(ExpandConstant('{sys}\sc.exe'), 'stop FleetLumaAgent', '',
           SW_HIDE, ewWaitUntilTerminated, ExitCode);
      Sleep(2500);
      Exec(ExpandConstant('{sys}\sc.exe'), 'delete FleetLumaAgent', '',
           SW_HIDE, ewWaitUntilTerminated, ExitCode);
    end;
  end;
end;

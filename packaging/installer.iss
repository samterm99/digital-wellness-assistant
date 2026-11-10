; Inno Setup script - per-user install, no admin rights. Build with packaging\build.ps1.
; Defines passed on the command line: SourceDir (PyInstaller onedir folder), OutDir.
#define AppNameTh "ผู้ช่วยสุขภาพดิจิทัล"
#define AppNameEn "Digital Wellness Assistant"
#define AppVersion "1.2.0"
#define AppExe "DigitalWellnessAssistant.exe"
#define AppUserModelId "DigitalWellness.Assistant"
#ifndef SourceDir
  #define SourceDir "..\..\DWA-build\dist\DigitalWellnessAssistant"
#endif
#ifndef OutDir
  #define OutDir "..\..\DWA-build\installer"
#endif

[Setup]
AppId={{6E0F4D52-3B7A-4C1E-9D2A-DA17E55A1B20}
AppName={#AppNameTh} ({#AppNameEn})
AppVersion={#AppVersion}
AppVerName={#AppNameTh} {#AppVersion}
AppPublisher={#AppNameEn}
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppNameEn}
VersionInfoDescription={#AppNameTh} Setup
DefaultDirName={localappdata}\Programs\DigitalWellnessAssistant
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutDir}
OutputBaseFilename=DigitalWellnessAssistant-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppNameTh} ({#AppNameEn})
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
StartupTask=เปิดผู้ช่วยสุขภาพดิจิทัลอัตโนมัติเมื่อเข้าสู่ Windows (Start automatically when I sign in to Windows)
LaunchApp=เปิดผู้ช่วยสุขภาพดิจิทัลเดี๋ยวนี้ (Start {#AppNameEn} now)
MigrateOld=พบทางลัด Startup รุ่นทดลอง (start.bat) ของโปรแกรมนี้:%n%1%n%nปิดการใช้งานทางลัดนี้เพื่อไม่ให้เปิดโปรแกรมซ้ำหรือไม่?%n(Disable this old test-version startup shortcut? It will be renamed, not deleted.)
KeepData=ต้องการลบการตั้งค่าและบันทึกการทำงานของผู้ช่วยสุขภาพดิจิทัลด้วยหรือไม่?%n(Also delete your settings and logs?)%n%nเลือก "No" เพื่อเก็บไว้ใช้ถ้าติดตั้งใหม่ภายหลัง

[Tasks]
Name: "startup"; Description: "{cm:StartupTask}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppNameTh}"; Filename: "{app}\{#AppExe}"; Parameters: "--launch"; WorkingDir: "{app}"; AppUserModelID: "{#AppUserModelId}"
; The existing startup flag keeps the "show control panel at startup" preference authoritative.
Name: "{userstartup}\{#AppNameTh}"; Filename: "{app}\{#AppExe}"; Parameters: "--launch --startup"; WorkingDir: "{app}"; Tasks: startup; AppUserModelID: "{#AppUserModelId}"

[Registry]
; Display name Windows shows as the sender of this app's notifications.
Root: HKCU; Subkey: "Software\Classes\AppUserModelId\{#AppUserModelId}"; ValueType: string; ValueName: "DisplayName"; ValueData: "{#AppNameTh}"; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#AppExe}"; Parameters: "--launch"; WorkingDir: "{app}"; Description: "{cm:LaunchApp}"; Flags: postinstall nowait skipifsilent

[Code]
// Reads target / arguments / working dir of a .lnk (Windows Script Host). False if unreadable.
function ReadShortcut(const Lnk: String; var Target, Args, WorkDir: String): Boolean;
var
  Shell, Sc: Variant;
begin
  Result := False;
  try
    Shell := CreateOleObject('WScript.Shell');
    Sc := Shell.CreateShortcut(Lnk);
    Target := Sc.TargetPath;
    Args := Sc.Arguments;
    WorkDir := Sc.WorkingDirectory;
    Result := True;
  except
  end;
end;

// Path of the experimental start.bat a Startup shortcut runs, or '' if it is not one.
// Only accepted when the .bat sits in a project folder (has src\wellness\__main__.py).
function LegacyBatOf(const Target, Args, WorkDir: String): String;
var
  Bat, Rest: String;
  P: Integer;
begin
  Result := '';
  Bat := '';
  if CompareText(ExtractFileName(Target), 'start.bat') = 0 then
    Bat := Target
  else if Pos('start.bat', Lowercase(Args)) > 0 then
  begin
    // cmd /c "C:\path\start.bat" [startup]  -> quoted path, else the shortcut's working dir
    Rest := Args;
    P := Pos('"', Rest);
    if P > 0 then
    begin
      Delete(Rest, 1, P);
      P := Pos('"', Rest);
      if P > 0 then Bat := Copy(Rest, 1, P - 1);
    end;
    if (CompareText(ExtractFileName(Bat), 'start.bat') <> 0) and (WorkDir <> '') then
      Bat := AddBackslash(WorkDir) + 'start.bat';
  end;
  if (Bat <> '') and FileExists(Bat) and
     FileExists(AddBackslash(ExtractFilePath(Bat)) + 'src\wellness\__main__.py') then
    Result := Bat;
end;

procedure CleanStartupShortcuts;
var
  Dir, Own, Target, Args, WorkDir, Bat, Lnk: String;
  FindRec: TFindRec;
begin
  Dir := ExpandConstant('{userstartup}');
  Own := ExpandConstant('{userstartup}\{#AppNameTh}.lnk');
  if not FindFirst(Dir + '\*.lnk', FindRec) then Exit;
  try
    repeat
      Lnk := Dir + '\' + FindRec.Name;
      if not ReadShortcut(Lnk, Target, Args, WorkDir) then Continue;
      if CompareText(Lnk, Own) = 0 then
      begin
        // our own shortcut name, removed (box unticked) only when it points at our exe
        if (not WizardIsTaskSelected('startup')) and
           (CompareText(Target, ExpandConstant('{app}\{#AppExe}')) = 0) then
          DeleteFile(Lnk);
      end
      else
      begin
        // someone else's shortcut: touched only if it is verifiably the old start.bat of this project
        Bat := LegacyBatOf(Target, Args, WorkDir);
        if (Bat <> '') and (not WizardSilent) and
           (MsgBox(FmtMessage(CustomMessage('MigrateOld'), [Lnk + #13#10 + Bat]),
                   mbConfirmation, MB_YESNO) = IDYES) then
          RenameFile(Lnk, Lnk + '.disabled-by-dwa');
      end;
    until not FindNext(FindRec);
  finally
    FindClose(FindRec);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then CleanStartupShortcuts;
end;

procedure StopRunningApp;
var
  Exe: String;
  Code: Integer;
begin
  Exe := ExpandConstant('{app}\{#AppExe}');
  if FileExists(Exe) then
  begin
    Exec(Exe, '--quit', '', SW_HIDE, ewWaitUntilTerminated, Code);
    Sleep(1500);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopRunningApp;  // upgrade: no second background process, no locked files
  Result := '';
end;

function InitializeUninstall: Boolean;
begin
  StopRunningApp;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // Settings/logs live in %LOCALAPPDATA%\DigitalWellnessAssistant. Kept unless the user agrees.
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    if MsgBox(ExpandConstant('{cm:KeepData}'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{localappdata}\DigitalWellnessAssistant'), True, True, True);
end;

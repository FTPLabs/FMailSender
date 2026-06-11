; ═══════════════════════════════════════════════════════════════════════════
;  FMail Sender — Inno Setup 6  (Web3 / Glassmorphism branded installer)
;  Design: deep space #050510, violet-cyan neon gradient
; ═══════════════════════════════════════════════════════════════════════════

#define MyAppName      "FMail Sender"
#define MyAppVersion   "2.1.0"
#define MyAppPublisher "FTPLabs"
#define MyAppURL       "https://fmailsender.app"
#define MyAppExeName   "FMailSender.exe"
#define BuildDir       "..\dist\FMailSender"

[Setup]
AppId={{B8C4D0E3-2F5A-6B9C-0D1E-3F4A5B6C7D8E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\FMailSender
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AllowNoIcons=no
; --- Web3 / Glassmorphism branded images ---
WizardStyle=modern
WizardSizePercent=120,110
WizardImageFile=wizard_sidebar.bmp
WizardSmallImageFile=wizard_header.bmp
OutputDir=..\dist\installer
OutputBaseFilename=FMailSender-{#MyAppVersion}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
MinVersion=10.0
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}";           Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Удалить {#MyAppName}";   Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";     Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\FMailSender\cache"
Type: filesandordirs; Name: "{userappdata}\FMailSender\logs"

[Registry]
Root: HKCU; Subkey: "Software\FTPLabs\FMailSender"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\FTPLabs\FMailSender"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"

[Code]
// ── Web3 / Glassmorphism palette (Inno Setup BGR hex) ───────────────────
// #050510 → $100505  | #0A0A1A → $1A0A0A
// #7C3AED → $ED3A7C  | #06B6D4 → $D4B606
// #E8E8FF → $FFE8E8  | #8888BB → $BB8888

procedure InitializeWizard();
var
  i: Integer;
begin
  // Deep space background
  WizardForm.Color := $100505;
  WizardForm.Font.Color := $FFE8E8;

  // Style all inner panels dark
  for i := 0 to WizardForm.ComponentCount - 1 do
  begin
    if WizardForm.Components[i] is TPanel then
      TPanel(WizardForm.Components[i]).Color := $0A0505;
  end;

  // Page name — neon violet
  WizardForm.PageNameLabel.Font.Color := $ED3A7C;
  WizardForm.PageNameLabel.Font.Style := [fsBold];

  // Page description — muted
  WizardForm.PageDescriptionLabel.Font.Color := $BB8888;

  // Next / Back / Install buttons — neon gradient sim (dark purple)
  WizardForm.NextButton.Font.Color := $FFE8E8;
  WizardForm.BackButton.Font.Color := $BB8888;
  WizardForm.CancelButton.Font.Color := $BB8888;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;

function GetUninstallString(): String;
var
  sPath, sStr: String;
begin
  sPath := ExpandConstant('Software\Microsoft\Windows\CurrentVersion\Uninstall\{#emit SetupSetting("AppId")}_is1');
  sStr  := '';
  if not RegQueryStringValue(HKLM, sPath, 'UninstallString', sStr) then
    RegQueryStringValue(HKCU, sPath, 'UninstallString', sStr);
  Result := sStr;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  sStr: String;
  iCode: Integer;
begin
  if (CurStep = ssInstall) and (GetUninstallString() <> '') then begin
    sStr := RemoveQuotes(GetUninstallString());
    Exec(sStr, '/SILENT /NORESTART /SUPPRESSMSGBOXES', '', SW_HIDE, ewWaitUntilTerminated, iCode);
  end;
end;

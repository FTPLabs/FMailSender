; ═══════════════════════════════════════════════════════════════
  ;  Email Sender Pro — Inno Setup Script
  ;  Компилятор: Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
  ;  Создаёт единый Setup.exe без лишних папок и архивов
  ; ═══════════════════════════════════════════════════════════════

  #define MyAppName      "Email Sender Pro"
  #define MyAppVersion   "1.0.0"
  #define MyAppPublisher "EmailSenderPro"
  #define MyAppURL       "https://emailsenderpro.app"
  #define MyAppExeName   "EmailSenderPro.exe"
  #define BuildDir       "..\\dist\\EmailSenderPro"

  [Setup]
  AppId={{A7B3C9D2-1E4F-5A8B-9C0D-2E3F4A5B6C7D}
  AppName={#MyAppName}
  AppVersion={#MyAppVersion}
  AppPublisher={#MyAppPublisher}
  AppPublisherURL={#MyAppURL}
  AppSupportURL={#MyAppURL}
  AppUpdatesURL={#MyAppURL}

  ; Директория установки — в AppData\Local (не требует прав администратора)
  DefaultDirName={localappdata}\EmailSenderPro
  DefaultGroupName={#MyAppName}
  DisableProgramGroupPage=yes
  AllowNoIcons=no

  ; Внешний вид установщика
  WizardStyle=modern
  WizardSizePercent=120,110

  ; Выходной файл — единый Setup.exe
  OutputDir=..\\dist\\installer
  OutputBaseFilename=EmailSenderPro-{#MyAppVersion}-Setup
  Compression=lzma2/ultra64
  SolidCompression=yes
  LZMAUseSeparateProcess=yes

  ; Требования
  MinVersion=10.0
  PrivilegesRequired=lowest
  PrivilegesRequiredOverridesAllowed=dialog

  [Languages]
  Name: "russian"; MessagesFile: "compiler:Languages\\Russian.isl"
  Name: "english"; MessagesFile: "compiler:Default.isl"

  [Tasks]
  Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

  [Files]
  ; Копируем всё содержимое папки dist/EmailSenderPro (exe + _internal)
  Source: "{#BuildDir}\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

  [Icons]
  ; BUG FIX: используем Filename: вместо DestPath: (правильный синтаксис Inno Setup)
  Name: "{group}\\{#MyAppName}";         Filename: "{app}\\{#MyAppExeName}"
  Name: "{group}\\Удалить {#MyAppName}"; Filename: "{uninstallexe}"
  Name: "{autodesktop}\\{#MyAppName}";   Filename: "{app}\\{#MyAppExeName}"; Tasks: desktopicon

  [Run]
  Filename: "{app}\\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

  [UninstallDelete]
  Type: filesandordirs; Name: "{userappdata}\\EmailSenderPro\\cache"
  Type: filesandordirs; Name: "{userappdata}\\EmailSenderPro\\logs"

  [Registry]
  Root: HKCU; Subkey: "Software\\EmailSenderPro\\EmailSenderPro"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
  Root: HKCU; Subkey: "Software\\EmailSenderPro\\EmailSenderPro"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"

  [Code]
  function InitializeSetup(): Boolean;
  begin
    Result := True;
  end;

  procedure InitializeWizard();
  begin
    WizardForm.Color := $0F0F11;
    WizardForm.Font.Color := $F4F4F5;
  end;

  function GetUninstallString(): String;
  var
    sUnInstPath: String;
    sUnInstallString: String;
  begin
    sUnInstPath := ExpandConstant('Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{#emit SetupSetting("AppId")}_is1');
    sUnInstallString := '';
    if not RegQueryStringValue(HKLM, sUnInstPath, 'UninstallString', sUnInstallString) then
      RegQueryStringValue(HKCU, sUnInstPath, 'UninstallString', sUnInstallString);
    Result := sUnInstallString;
  end;

  function IsUpgrade(): Boolean;
  begin
    Result := (GetUninstallString() <> '');
  end;

  function UnInstallOldVersion(): Integer;
  var
    sUnInstallString: String;
    iResultCode: Integer;
  begin
    Result := 0;
    sUnInstallString := GetUninstallString();
    if sUnInstallString <> '' then begin
      sUnInstallString := RemoveQuotes(sUnInstallString);
      if Exec(sUnInstallString, '/SILENT /NORESTART /SUPPRESSMSGBOXES', '', SW_HIDE, ewWaitUntilTerminated, iResultCode) then
        Result := 3
      else
        Result := 2;
    end else
      Result := 1;
  end;

  procedure CurStepChanged(CurStep: TSetupStep);
  begin
    if (CurStep = ssInstall) then begin
      if (IsUpgrade()) then
        UnInstallOldVersion();
    end;
  end;
  
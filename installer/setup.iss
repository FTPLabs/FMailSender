; ═══════════════════════════════════════════════════════════════
;  Email Sender Pro — Inno Setup Script
;  Компилятор: Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
;  Использование: iscc setup.iss
; ═══════════════════════════════════════════════════════════════

#define MyAppName      "Email Sender Pro"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "EmailSenderPro"
#define MyAppURL       "https://emailsenderpro.app"
#define MyAppExeName   "EmailSenderPro.exe"
#define BuildDir       "..\dist\EmailSenderPro"

[Setup]
AppId={{A7B3C9D2-1E4F-5A8B-9C0D-2E3F4A5B6C7D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Директория установки
DefaultDirName={autopf}\EmailSenderPro
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AllowNoIcons=no

; Внешний вид установщика
WizardStyle=modern
WizardSizePercent=120,110
SetupIconFile=..\assets\icons\app.ico
UninstallDisplayIcon={app}\EmailSenderPro.exe

; Лицензионное соглашение
; LicenseFile=..\LICENSE.txt

; Выходной файл
OutputDir=..\dist\installer
OutputBaseFilename=EmailSenderPro-{#MyAppVersion}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Требования
MinVersion=10.0
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Подписание кода (раскомментируйте при наличии сертификата)
; SignTool=signtool sign /td sha256 /fd sha256 /tr http://timestamp.digicert.com /d "Email Sender Pro" $f

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
russian.WelcomeLabel2=Это мастер установит [name/ver] на ваш компьютер.%n%nРекомендуется закрыть все другие приложения перед продолжением.%n%nНажмите Далее для продолжения или Отмена для выхода.
russian.SelectComponents=Выберите компоненты для установки
russian.FinishedHeadingLabel=Установка завершена
russian.FinishedLabelNoIcons=Нажмите Завершить для выхода из мастера установки.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1

[Files]
; Основные файлы приложения (из папки dist)
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Ярлыки не требуют отдельной секции Files

[Icons]
Name: "{group}\{#MyAppName}";          DestPath: "{app}\{#MyAppExeName}"
Name: "{group}\Удалить {#MyAppName}";  DestPath: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";    DestPath: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; DestPath: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Удаляем данные приложения при деинсталляции (кроме лицензии)
Type: filesandordirs; Name: "{userappdata}\EmailSenderPro\cache"
Type: filesandordirs; Name: "{userappdata}\EmailSenderPro\logs"

[Registry]
; Регистрация приложения в Add/Remove Programs с дополнительными данными
Root: HKCU; Subkey: "Software\EmailSenderPro\EmailSenderPro"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\EmailSenderPro\EmailSenderPro"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"

[Code]
// ──────────────────────────────────────────────
// Проверка версии .NET / VCRedist (не требуется для Python .exe)
// ──────────────────────────────────────────────

function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure InitializeWizard();
begin
  // Кастомные цвета страниц мастера
  WizardForm.Color := $0F0F11;
  WizardForm.Font.Color := $F4F4F5;
end;

function GetUninstallString(): String;
var
  sUnInstPath: String;
  sUnInstallString: String;
begin
  sUnInstPath := ExpandConstant('Software\Microsoft\Windows\CurrentVersion\Uninstall\{#emit SetupSetting("AppId")}_is1');
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

; FMailSender Portable Launcher
; Usage: makensis portable.nsi
; Output: FMailSender.exe — единый portable EXE, установка не нужна.
;
; Поведение:
;   1. Мгновенно распаковывает FMailSender.exe + fmail-core.exe в %TEMP%\FMailSender
;   2. Запускает FMailSender.exe и ждёт закрытия
;   3. После закрытия — автоматически удаляет временные файлы из TEMP
;
; Файлы для dist_portable\ готовит CI (release.yml шаг "Build portable single EXE").

Unicode true
SetCompressor /SOLID lzma
OutFile "FMailSender.exe"
InstallDir "$TEMP\FMailSender"
RequestExecutionLevel user
SilentInstall silent

Section
  SetOutPath "$INSTDIR"
  File "dist_portable\FMailSender.exe"
  File "dist_portable\fmail-core.exe"
  ExecWait '"$INSTDIR\FMailSender.exe"'
  Delete "$INSTDIR\FMailSender.exe"
  Delete "$INSTDIR\fmail-core.exe"
  RMDir "$INSTDIR"
SectionEnd

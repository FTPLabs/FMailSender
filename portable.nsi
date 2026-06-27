; FMailSender Portable Launcher
; Usage: makensis portable.nsi
; Creates MailSender.exe — double-click to run, no installation required.
; Silently extracts both executables to %TEMP%\FMailSender, runs FMailSender.exe,
; waits for it to close, then cleans up temp files automatically.

Unicode true
SetCompressor /SOLID lzma
OutFile "MailSender.exe"
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

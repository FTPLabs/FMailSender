; FMailSender Portable Launcher
; Usage: makensis /DVERSION=6.0.2 portable.nsi
; Creates a single .exe that silently extracts to %TEMP%\FMailSender,
; runs FMailSender.exe, waits for it to close, then cleans up.
; No installation, no registry changes, no admin rights needed.

Unicode true
SetCompressor /SOLID lzma

!ifndef VERSION
  !define VERSION "6.0.2"
!endif

OutFile "FMailSender-v${VERSION}-portable.exe"
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

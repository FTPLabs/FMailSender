; FMailSender Portable Launcher v3 — Persistent Install
  ; Behaviour:
  ;   1. Extracts FMailSender.exe + fmail-core.exe to %LOCALAPPDATA%\FMailSender\
  ;      (persistent — files stay between runs, updated on each new version run)
  ;   2. Creates a Desktop shortcut pointing to the installed EXE
  ;   3. Launches FMailSender.exe immediately (Exec = non-blocking, launcher exits)
  ;
  ; No installer wizard. No UAC prompt. No TEMP cleanup.
  ; User experience: download → double-click → app opens. Done.
  ;
  ; CI build (from repo root, files staged in dist_portable\):
  ;   makensis /V2 /DOUTFILE=FMailSender-v6.7.0.exe /DTARGET=x86_64-pc-windows-msvc portable.nsi

  Unicode true
  SetCompressor /SOLID lzma
  Name "FMailSender"
  InstallDir "$LOCALAPPDATA\FMailSender"
  RequestExecutionLevel user
  SilentInstall silent

  !ifndef OUTFILE
    !define OUTFILE "FMailSender.exe"
  !endif
  !ifndef TARGET
    !define TARGET "x86_64-pc-windows-msvc"
  !endif

  OutFile "${OUTFILE}"

  Section
    SetOutPath "$INSTDIR"
    File "dist_portable\FMailSender.exe"
    File "dist_portable\fmail-core-${TARGET}.exe"

    ; Desktop shortcut — user can double-click this for future launches
    CreateShortcut "$DESKTOP\FMailSender.lnk" "$INSTDIR\FMailSender.exe" "" "$INSTDIR\FMailSender.exe" 0

    ; Launch immediately — Exec is non-blocking, launcher exits after starting app
    Exec '"$INSTDIR\FMailSender.exe"'
  SectionEnd
  
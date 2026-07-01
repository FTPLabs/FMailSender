; FMailSender Portable Launcher v4 — Single-EXE (embedded core)
  ; Behaviour:
  ;   1. Extracts FMailSender.exe to %LOCALAPPDATA%\FMailSender\
  ;      (fmail-core is embedded inside FMailSender.exe — no separate sidecar file)
  ;   2. Creates a Desktop shortcut pointing to the installed EXE
  ;   3. Launches FMailSender.exe immediately (Exec = non-blocking, launcher exits)
  ;
  ; No installer wizard. No UAC prompt. No TEMP cleanup.
  ; User experience: download → double-click → app opens. Done.
  ;
  ; CI build (from repo root, files staged in dist_portable\):
  ;   makensis /V2 /DOUTFILE=FMailSender-v6.7.4.exe portable.nsi

  Unicode true
  SetCompressor /SOLID lzma
  Name "FMailSender"
  InstallDir "$LOCALAPPDATA\FMailSender"
  RequestExecutionLevel user
  SilentInstall silent

  !ifndef OUTFILE
    !define OUTFILE "FMailSender.exe"
  !endif

  OutFile "${OUTFILE}"

  Section
    SetOutPath "$INSTDIR"
    File "dist_portable\FMailSender.exe"

    ; Desktop shortcut — user can double-click this for future launches
    CreateShortcut "$DESKTOP\FMailSender.lnk" "$INSTDIR\FMailSender.exe" "" "$INSTDIR\FMailSender.exe" 0

    ; Launch immediately — Exec is non-blocking, launcher exits after starting app
    Exec '"$INSTDIR\FMailSender.exe"'
  SectionEnd

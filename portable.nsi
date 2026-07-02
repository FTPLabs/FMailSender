; FMailSender Portable Launcher — LEGACY (kept for reference)
; ─────────────────────────────────────────────────────────────────────────────
; NOTE: This NSIS script is NO LONGER USED in CI as of v6.9.
; The release workflow now ships the raw Tauri exe (fmail-sender.exe renamed
; to FMailSender-vX.X.X.exe) directly without any NSIS wrapper.
;
; Reason: The previous NSIS approach created a Desktop shortcut and installed
; the app to %LOCALAPPDATA% — violating the "downloaded file IS the final app"
; requirement. The raw Tauri exe already embeds fmail-core via include_bytes!()
; and is truly self-contained.
;
; This file is kept only as a reference for manual builds.
; ─────────────────────────────────────────────────────────────────────────────

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

  ; NOTE: Desktop shortcut REMOVED (v6.9) — no user-visible files should be created.
  ; The previous line was: CreateShortcut "$DESKTOP\FMailSender.lnk" ...
  ; Removed to match the "downloaded file IS the final app" contract.

  ; Launch immediately — Exec is non-blocking, launcher exits after starting app
  Exec '"$INSTDIR\FMailSender.exe"'
SectionEnd

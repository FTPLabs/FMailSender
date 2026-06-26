# Windows EXE Build — FMailSender v6

  ## Build pipeline

  ```
  Python → PyInstaller → fmail-core.exe → src-tauri/binaries/
  React  → npm build  → ui/dist/
  Tauri  → cargo tauri build → target/release/bundle/*.exe + *.msi
  ```

  ## PyInstaller spec: fmail-core.spec

  Entry: main.py (uvicorn core.server:app :7531)
  Output: fmail-core.exe (onefile, no-console, UPX)
  Critical hidden imports: uvicorn.loops.auto, fastapi, cryptography.fernet

  Binary goes to: src-tauri/binaries/fmail-core-x86_64-pc-windows-msvc.exe

  ## GitHub Actions trigger

  Push tag: git tag v6.x.x && git push origin v6.x.x
  Manual: Actions → Build & Release → Run workflow → enter version

  ## Sidecar in tauri.conf.json

  ```json
  "bundle": { "externalBin": ["binaries/fmail-core"] }
  ```

  ## Expected sizes

  fmail-core.exe: 25-45 MB | FMailSender installer: 30-55 MB
  
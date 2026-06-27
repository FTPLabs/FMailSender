---
name: windows-exe-build
description: Сборка Windows EXE для FMailSender v6 через Tauri v2 + PyInstaller + React/Vite. Весь pipeline, диагностика ошибок.
---

# Windows EXE Build — FMailSender v6

## Pipeline сборки

```
Python → PyInstaller → fmail-core.exe → src-tauri/binaries/
React  → npm run build → ui/dist/
Tauri  → tauri build → target/release/bundle/*.exe + *.msi
```

## PyInstaller spec: fmail-core.spec

Точка входа: `main.py` (запускает `core/server.py` на uvicorn :7531)
Выход: `fmail-core.exe` (onefile, no-console, без UPX)

**Критические настройки:**
```python
upx=False           # UPX не установлен на GitHub CI — обязательно False
console=False       # без консольного окна
```

**Hidden imports (обязательные):**
- `uvicorn.loops.auto`, `fastapi`, `cryptography.fernet`
- Все модули uvicorn protocol

**Бинарный файл:** `src-tauri/binaries/fmail-core-x86_64-pc-windows-msvc.exe`

## Триггер GitHub Actions

```bash
# По тегу:
git tag v6.x.x && git push origin v6.x.x

# Вручную:
Actions → Build & Release → Run workflow → version: 6.0.1
```

## Sidecar в tauri.conf.json

```json
"bundle": { "externalBin": ["binaries/fmail-core"] }
```
Tauri копирует `fmail-core-x86_64-pc-windows-msvc.exe` → инсталлятор.

## Иконки

```yaml
# В CI (release.yml):
- name: Install tauri-cli
  run: npm install -g @tauri-apps/cli@^2
  
- name: Generate icons
  run: tauri icon assets/images/fmail_logo.png
```

Локально:
```bash
npm install -g @tauri-apps/cli@^2
tauri icon assets/images/fmail_logo.png
# → src-tauri/icons/ (32x32.png, 128x128.png, icon.ico, ...)
```

## Vite — КРИТИЧНО для prod

```typescript
// ui/vite.config.ts — обязательно!
base: './'
```
Без этого WebView2 в Tauri не загрузит JS/CSS (пути будут абсолютными `/assets/...`).

## Ожидаемые размеры

`fmail-core.exe`: 25–45 МБ | Инсталлятор FMailSender: 30–55 МБ

## Диагностика ошибок CI

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `error: no such subcommand: tauri` | tauri-cli не установлен | `npm install -g @tauri-apps/cli@^2` |
| Blank WebView / белый экран | `base: './'` не задан | Добавить в vite.config.ts |
| `icon file not found` | icons/ отсутствует | `tauri icon assets/images/fmail_logo.png` |
| `sidecar not found` | Неверное имя binary | Переименовать в `-x86_64-pc-windows-msvc.exe` |
| `beforeBuildCommand failed` | Неверный путь `cd ui` из src-tauri/ | `beforeBuildCommand: ""` в tauri.conf.json |
| PyInstaller: UPX not found | upx=True, UPX не установлен | `upx=False` в spec |
| Release tag = "main" | `github.ref_name` при dispatch | Использовать `steps.tag.outputs.tag` |

## После сборки

```
src-tauri/target/release/bundle/
├── nsis/
│   └── FMailSender_6.0.0_x64-setup.exe   ← основной инсталлятор
└── msi/
    └── FMailSender_6.0.0_x64_en-US.msi   ← MSI альтернатива
```

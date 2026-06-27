---
name: tauri-fastapi
description: Архитектура Tauri v2 + Python FastAPI для FMailSender v6. Как добавлять эндпоинты, экраны, зависимости. Порядок CI-сборки.
---

# Tauri + FastAPI Architecture — FMailSender v6

## Как всё работает

```
[Windows пользователь] открывает FMailSender.exe
  → Tauri main.rs запускается
  → Ищет fmail-core.exe в resource_dir() → запускает как sidecar (порт 7531)
  → Fallback: python main.py (dev-режим)
  → Ждёт до 30с, пока :7531 не примет соединения
  → WebView2 загружает встроенный ui/dist/ (prod) или http://localhost:5173 (dev)
```

## Добавление новой функции

1. Добавить эндпоинт в `core/server.py`
2. Добавить тип в `core/models.py` если нужно
3. Добавить API-вызов в `ui/src/api.ts`
4. Добавить/обновить страницу в `ui/src/pages/`

## Dev-режим (локально)

```bash
# Терминал 1: Python core
pip install -r requirements.txt
python main.py          # FastAPI на :7531

# Терминал 2: React UI
cd ui && npm install && npm run dev  # Vite на :5173

# Терминал 3: Tauri dev (опционально)
tauri dev
```

## CI/CD порядок сборки (release.yml)

```
1. npm install && npm run build    → ui/dist/
2. npm install -g @tauri-apps/cli  → CLI для tauri команд
3. tauri icon assets/images/fmail_logo.png → src-tauri/icons/
4. pyinstaller fmail-core.spec     → src-tauri/binaries/fmail-core.exe
5. cp fmail-core.exe → fmail-core-x86_64-pc-windows-msvc.exe  (sidecar naming)
6. tauri build                     → src-tauri/target/release/bundle/
```

## Vite — обязательные настройки для Tauri

```typescript
// ui/vite.config.ts
export default defineConfig({
  base: './',  // КРИТИЧНО: без этого WebView не загружает ресурсы в prod
  ...
})
```

## CORS

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # работает в dev (5173) и prod (Tauri WebView)
)
```

## Sidecar naming convention

Tauri требует именования: `<name>-<target-triple>.exe`
```
fmail-core.exe → fmail-core-x86_64-pc-windows-msvc.exe
```
`tauri.conf.json` → `"externalBin": ["binaries/fmail-core"]`

## Порты

| Сервис   | Порт | Назначение                  |
|----------|------|-----------------------------|
| FastAPI  | 7531 | HTTP API (Python core)      |
| Vite dev | 5173 | React фронтенд (dev only)   |
| Tauri    | —    | Встраивает dist/ в prod     |

## Иконки

Генерируются автоматически в CI:
```bash
tauri icon assets/images/fmail_logo.png
# → src-tauri/icons/32x32.png, 128x128.png, icon.ico, и т.д.
```

Локально: установить `@tauri-apps/cli` глобально или через `ui/package.json`.

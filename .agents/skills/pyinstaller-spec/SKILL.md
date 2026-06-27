---
name: pyinstaller-spec
description: PyInstaller spec для FMailSender v6 (FastAPI backend). Скрытые импорты, data-файлы, onefile сборка. Активируй при ошибках сборки fmail-core.exe.
---

# PyInstaller Spec — FMailSender v6 (FastAPI core)

## Команда сборки

```bash
# Из корня репозитория:
pyinstaller fmail-core.spec \
  --distpath src-tauri/binaries \
  --noconfirm

# CI (PowerShell):
pyinstaller fmail-core.spec `
  --distpath "src-tauri/binaries" `
  --workpath "C:/tmp/pyinstaller-build" `
  --noconfirm
```

## Обязательные настройки spec

```python
# PyInstaller >= 6.0: НЕТ cipher= аргумента
pyz = PYZ(a.pure, a.zipped_data)  # ✅

# UPX: ВЫКЛЮЧИТЬ на CI (UPX не установлен)
upx=False  # ✅
# upx=True  # ❌ GitHub runner не имеет UPX

# console=False: без консольного окна
console=False  # ✅
```

## Data files

```python
datas = [(str(ROOT / "core"), "core")]
if (ROOT / "data").exists():
    datas.append((str(ROOT / "data"), "data"))
if (ROOT / "i18n").exists():
    datas.append((str(ROOT / "i18n"), "i18n"))
```

## Частые ошибки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `ModuleNotFoundError: uvicorn.loops` | Не в hiddenimports | Добавить uvicorn скрытые импорты |
| `UPX is not available` | upx=True, UPX не установлен | Изменить на `upx=False` |
| `cipher=block_cipher` SyntaxError | Устаревший синтаксис | Убрать `cipher=` из PYZ() |
| `FileNotFoundError: data/spam_words.json` | data/ не в datas | Добавить в `datas` |
| Runtime ImportError на cryptography | Не в hiddenimports | Добавить `cryptography.hazmat.backends.openssl` |

## Sidecar naming для Tauri

```bash
# После pyinstaller:
cp src-tauri/binaries/fmail-core.exe \
   src-tauri/binaries/fmail-core-x86_64-pc-windows-msvc.exe
```

## Проверка после сборки

```powershell
$exe = "src-tauri/binaries/fmail-core-x86_64-pc-windows-msvc.exe"
if (Test-Path $exe) {
    $sz = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host "OK: fmail-core.exe $sz MB"  # норма: 25-45 MB
} else {
    Write-Error "FAIL: sidecar binary не найден"
}
```

## Добавление новой Python зависимости в EXE

1. Добавить в `requirements.txt`
2. Если pure Python — PyInstaller найдёт автоматически
3. Если нужен hidden import — добавить в список `ALL_HIDDEN` в spec
4. Если нужны data-файлы — добавить в `datas`
5. Пересобрать: `pyinstaller fmail-core.spec --distpath src-tauri/binaries --noconfirm`

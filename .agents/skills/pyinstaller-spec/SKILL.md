---
name: pyinstaller-spec
description: PyInstaller spec файл и build.py для FMailSender — скрытые импорты, data files, onefile сборка. Активируй при ошибках сборки EXE.
---

# PyInstaller Spec — FMailSender

## build.py — главный скрипт

```python
# build.py вызывает PyInstaller с нужными параметрами
import subprocess, sys

subprocess.run([
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--name", "FMailSender",
    "--icon", "assets/icon.ico",
    "--add-data", "data;data",
    "--add-data", "i18n;i18n",
    "--add-data", "templates;templates",
    "--hidden-import", "aiosmtplib",
    "--hidden-import", "socks",
    "--hidden-import", "cryptography",
    "--hidden-import", "PyQt6.sip",
    "main.py"
], check=True)
```

## Частые ошибки сборки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| ModuleNotFoundError в runtime | Hidden import | Добавить --hidden-import |
| FileNotFoundError для data файла | Data не включён | --add-data "src;dst" |
| Icon not found | Путь к иконке неверный | Проверить assets/icon.ico |
| PyQt6 crash | PyQt6.sip не включён | --hidden-import PyQt6.sip |

## Добавление новой зависимости в EXE

1. Добавить в `requirements.txt`
2. Если это pure Python пакет — PyInstaller найдёт сам
3. Если нужен hidden import:
   - `--hidden-import mypackage`
   - или в spec файле: `hiddenimports=['mypackage']`
4. Если нужны data файлы:
   - `--add-data "src_dir;dst_dir"` (Windows: `;` разделитель)

## Проверка размера EXE

После сборки проверяем:
```powershell
$size = [math]::Round((Get-Item 'dist\FMailSender.exe').Length / 1MB, 1)
Write-Host "EXE: $size MB"
# Норма: 50-150 MB для PyQt6 приложения
```

## Антивирус ложные срабатывания

PyInstaller EXE часто помечается антивирусом как подозрительный.
Решение: подпись кода (Code Signing Certificate) или исключение.
Текущий статус: без подписи — пользователи должны добавить в исключения.

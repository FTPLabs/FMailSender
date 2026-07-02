---
name: release-portable-guard
description: Защищает процесс выпуска portable EXE для FMailSender v6.9+. Активируй при изменении release.yml, вопросах о дистрибуции, если пользователь жалуется на создание файлов при запуске, или при попытках вернуть NSIS обёртку.
---

# Release Portable Guard — FMailSender v6.9+

## Архитектура дистрибуции (v6.9+)

```
PyInstaller → fmail-core-x86_64-pc-windows-msvc.exe
  ↓ include_bytes!() в main.rs
Tauri build → fmail-sender.exe  (содержит Python-ядро ВНУТРИ)
  ↓ переименование в CI
FMailSender-v{version}.exe  ← ЭТО ФИНАЛЬНЫЙ .EXE для пользователя
```

## Правило: НЕТ NSIS обёртке

**ЗАПРЕЩЕНО** использовать portable.nsi или любой NSIS wrapper в CI.

Причина: NSIS launcher при запуске:
1. Устанавливал FMailSender.exe в %LOCALAPPDATA% (создавал новый файл)
2. Создавал ярлык на рабочем столе (нарушало требование)
3. Запускал из %LOCALAPPDATA%, а не из скачанного файла

Это нарушало контракт: «скачал → запустил → приложение открылось, ничего нового не создалось».

## Что происходит при запуске финального EXE

```
Пользователь двойной клик FMailSender-v6.9.0.exe
  → Rust extract_core() извлекает fmail-core-{version}.exe
    в %LOCALAPPDATA%\FMailSender\core\  (первый запуск — один раз)
  → AV сканирует (10-30с при первом запуске, потом кэш)
  → Python FastAPI сервер стартует на 127.0.0.1:7531
  → WebView2 окно открывается
  → GET /api/license → проверка на fmail.shop с HWID
  → Интерфейс готов
```

Извлечение в %LOCALAPPDATA%\FMailSender\core\ — нормальное поведение,
аналогично любому приложению. НЕ является проблемой.
Это НЕ «рабочий стол» и не «видимый пользователю файл».

## Шаг "Package portable EXE" в release.yml

```powershell
# ПРАВИЛЬНО: копируем сырой Tauri exe
Copy-Item $appExePath "FMailSender-v$ver.exe" -Force

# НЕПРАВИЛЬНО: использовать NSIS
# & makensis /DOUTFILE=... portable.nsi  ← НЕ ДЕЛАТЬ
```

## Проверка правильности сборки

```powershell
# Финальный EXE должен быть > 20 MB (Python core embedded)
$sz = [math]::Round((Get-Item "FMailSender-v*.exe").Length / 1MB, 1)
if ($sz -lt 15) { throw "EXE слишком маленький — ядро не встроено" }

# Проверка PyInstaller маркеров внутри EXE
$bytes = [System.IO.File]::ReadAllBytes("FMailSender-v*.exe")
$text = [System.Text.Encoding]::Latin1.GetString($bytes)
if (-not $text.Contains("MEI") -and -not $text.Contains("PyInstaller")) {
    Write-Warning "PyInstaller маркеры не найдены — проверьте что PyInstaller запускался ДО tauri build"
}
```

## Порядок шагов в CI (КРИТИЧНО)

```
1. Python deps (pip install)
2. Python import check
3. PyInstaller → src-tauri/binaries/fmail-core-x86_64-pc-windows-msvc.exe
4. UI Vite build → ui/dist/
5. tauri build → src-tauri/target/x86_64-pc-windows-msvc/release/fmail-sender.exe
6. Verify core embedded (размер + маркеры)
7. Переименовать fmail-sender.exe → FMailSender-v{ver}.exe
8. GitHub Release с этим файлом
```

**Шаг 3 ОБЯЗАТЕЛЬНО ПЕРЕД шагом 5** — иначе include_bytes!() включит в сборку
пустой/старый бинарь, и пользователь получит нерабочий EXE без Python-ядра.

## WebView2

tauri.conf.json: `"webviewInstallMode": { "type": "embedBootstrapper" }`

При запуске Tauri проверяет наличие WebView2. Если нет (редко на Win10 2004+):
- Скачивает и устанавливает тихо, без участия пользователя
- Win10 2004+ и Win11 имеют WebView2 из коробки

НЕ нужно менять на offlineInstaller — это увеличит EXE на ~150MB без реальной пользы.

## Частые ошибки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| EXE создаёт файл на рабочем столе | Использован NSIS portable.nsi | Убрать NSIS, шипить сырой exe |
| EXE < 20 MB в release | PyInstaller не запускался до tauri build | Проверить порядок шагов |
| "core may not be embedded" | include_bytes! получил старый бинарь | Пересобрать с --noconfirm |
| AV удалил fmail-core при первом запуске | Windows Defender quarantine | Добавить %LOCALAPPDATA%\FMailSender в исключения |
| Пустой экран после запуска | WebView2 скачивается (первый запуск без WebView2) | Подождать 30-60с |

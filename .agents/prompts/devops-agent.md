# DevOps Agent — FMailSender

## Роль
DevOps инженер FMailSender v6. Управляешь сборками EXE, GitHub Actions, релизами.

## Архитектура сборки (v6)
```
React (Vite) → ui/dist/
Python (PyInstaller) → src-tauri/binaries/fmail-core.exe
Tauri CLI → src-tauri/target/release/fmail-sender.exe
NSIS (portable.nsi) → MailSender.exe  ← финальный артефакт
```

## Скиллы при старте (загрузи все)
- `.agents/skills/windows-exe-build/SKILL.md`
- `.agents/skills/build-guard/SKILL.md`
- `.agents/skills/changelog-guard/SKILL.md`
- `.agents/skills/pyinstaller-spec/SKILL.md`

## Репозиторий
- Owner: FTPLabs
- Repo: FMailSender
- Branch: main
- Token: в attached_assets (НИКОГДА не показывай!)

## Процесс релиза

**Шаг 1:** Обновить `core/_version.py` → `APP_VERSION = "X.Y.Z"`

**Шаг 2:** Обновить версию в `src-tauri/tauri.conf.json` (поле "version")

**Шаг 3:** Обновить версию в `src-tauri/Cargo.toml` (поле version = "X.Y.Z")

**Шаг 4:** Добавить запись в `CHANGELOG.md`

**Шаг 5:** Запушить файлы через GitHub Tree API

**Шаг 6:** Запустить release workflow через workflow_dispatch:
```javascript
POST /repos/FTPLabs/FMailSender/actions/workflows/release.yml/dispatches
{ "ref": "main", "inputs": { "version": "X.Y.Z", "prerelease": false } }
```

**Шаг 7:** Мониторить сборку (~60-90 мин на Windows runner)

## GitHub Actions Workflows (актуальные)

| Workflow | Файл | Триггер | Действие |
|----------|------|---------|---------|
| Build & Release | release.yml | tag v* или dispatch | PyInstaller + Vite + Tauri + NSIS → MailSender.exe |
| CI Checks | ci.yml | push/PR на main | Python lint, TSC, Rust clippy, smoke tests |
| Python Syntax Check | syntax-check.yml | любой push | py_compile всех .py файлов |
| Secret & Security Scan | secret-scan.yml | любой push | ripgrep на секреты |

## Проверка статуса сборки

```javascript
// GET /repos/FTPLabs/FMailSender/actions/runs?per_page=5
// status: "in_progress" / "completed"
// conclusion: "success" / "failure" / null
// GET /repos/FTPLabs/FMailSender/actions/runs/{id}/jobs
// → шаги: PyInstaller, Vite build, Tauri build, NSIS
```

## Если сборка провалилась

1. Читай jobs → шаги → найди Failed step
2. Частые причины:
   - Новая зависимость не в `requirements.txt`
   - Hidden import нужен в `fmail-core.spec` (hiddenimports)
   - `ui/dist/` не создался (npm run build ошибка)
   - `fmail-core.exe` < 5 MB → PyInstaller упал тихо
   - NSIS: `portable.nsi` ссылается на несуществующий файл
3. Исправь → запушь → перезапусти workflow

## Проверка перед релизом (build-guard)

```bash
# 1. Vite base path (КРИТИЧНО для Tauri)
grep -n "base:" ui/vite.config.ts
# Должно быть: base: './'

# 2. Версии согласованы
python3 -c "from core._version import APP_VERSION; print(APP_VERSION)"
grep '"version"' src-tauri/tauri.conf.json
grep '^version' src-tauri/Cargo.toml

# 3. fmail-core.spec включает все модули
grep "hiddenimports" fmail-core.spec
```

## НИКОГДА не коммитить
- `data/accounts.json` (пароли пользователей)
- `.env` файлы
- `*.db` базы данных
- `src-tauri/target/` (артефакты Rust-сборки)
- `ui/dist/` (артефакты Vite-сборки)

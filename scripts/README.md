# scripts/

  ## toggle_and_build.py — Сборка EXE без лимитов Actions

  Обходит лимит GitHub Actions (2 000 мин/мес) на приватных репо, временно делая репо публичным.

  ### Предварительные требования

  1. Создайте Personal Access Token с правами **repo** + **admin:repo**:
     → https://github.com/settings/tokens

  2. Добавьте токен как GitHub Secret `ADMIN_PAT`:
     → Репозиторий → Settings → Secrets and variables → Actions → New

  3. Установите зависимости:
     ```bash
     pip install requests
     ```

  ### Использование

  ```bash
  export GITHUB_TOKEN=ghp_ваш_токен
  python scripts/toggle_and_build.py v3.5.4
  ```

  Флаги:
  - `--no-wait` — не ждать завершения (workflow сам вернёт приватность)
  - `--timeout 60` — таймаут ожидания в минутах (по умолчанию 40)

  ### Схема работы

  ```
  toggle_and_build.py
    │
    ├─ 1. PATCH /repos/{repo}  →  private: false   (публичный)
    │
    ├─ 2. POST /workflows/build.yml/dispatches     (запускаем сборку)
    │
    ├─ 3. Ждём завершения workflow...
    │
    └─ 4. workflow restore-privacy job:
           PATCH /repos/{repo}  →  private: true   (приватный ←)
  ```

  ### Почему это безопасно

  - Репо публичен **только во время сборки** (~15-25 минут)
  - Репо не содержит секретов в коде (GATE-3 secret scan блокирует коммиты)
  - Даже при падении сборки — `restore-privacy` запускается с `if: always()`
  - При падении самого workflow — скрипт принудительно делает репо приватным

  ### Требования к ADMIN_PAT

  Токен должен иметь:
  - `repo` (полный доступ к репозиторию)
  - `delete_repo` или `admin:repo` (для изменения видимости)

  Создать: https://github.com/settings/tokens/new?scopes=repo,delete_repo
  
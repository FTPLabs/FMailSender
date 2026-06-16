---
  name: secret-guard
  description: Сканирует Python-файлы и весь репозиторий на утечку секретов перед пушем или сборкой .exe. Обнаруживает IP-адреса, токены, пароли, ключи API, приватные ключи, URL лицензионного сервера, структуру ключей лицензий. Активируй ОБЯЗАТЕЛЬНО перед любым git push, созданием релиза или сборкой PyInstaller.
  ---

  # Secret Guard — Сканер Утечки Секретов и Защита Проекта

  ## Когда использовать

  - **ОБЯЗАТЕЛЬНО** перед каждым `git push` или `git commit`
  - Перед сборкой `.exe` через PyInstaller / GitHub Actions
  - При добавлении нового кода, работающего с API, базами данных, сетью
  - При ревью Pull Request от внешних контрибьюторов
  - Когда пользователь сообщает: "токен утёк", "пароль попал в репо", "credentials в коде"

  ## Что ищем

  ### 🔴 Критично — БЛОКИРУЕМ push

  | Тип | Пример паттерна |
  |---|---|
  | GitHub токены | `ghp_[A-Za-z0-9]{36}`, `github_pat_...` |
  | Telegram токены | `\d{8,12}:[A-Za-z0-9_-]{35}` |
  | OpenAI API ключи | `sk-[A-Za-z0-9]{48}`, `sk-proj-...` |
  | AWS ключи | `AKIA[0-9A-Z]{16}` |
  | Приватные ключи | `-----BEGIN.*PRIVATE KEY-----` |
  | Пароли в коде | `password\s*=\s*["'][^"']{6,}["']` |
  | **Hardcoded IP** | `["']\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}["']` в Python-файлах |
  | JWT токены | `eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+` |
  | **URL лицензионного сервера** | любой hardcoded https://IP или домен в license.py |
  | **Структура ключей лицензий** | `KEY_PREFIX` значение не должно быть хардкодом в публичном коде |
  | **HWID алгоритм** | детали HWID-генерации (CPU/MAC/disk) не должны описываться в README/комментариях |
  | **Пароли SSH/VPS** | `root@\d+\.\d+\.\d+\.\d+`, `password=`, учётные данные сервера |

  ### 🟡 Предупреждение — требует ревью

  | Тип | Пример |
  |---|---|
  | IP в конфиге | IP-адрес как дефолтное значение ENV |
  | `verify=False` | SSL проверка отключена без комментария |
  | Чувствит. файлы | `*.env`, `*.pem`, `*.key`, `*.p12` |
  | `TODO: remove` | Временный хардкод, который забыли убрать |
  | **Download URL захардкожен** | URL для скачивания .exe в публичном коде |
  | **Структура БД лицензий** | таблицы и поля не должны быть в README |

  ## Правила защиты от кражи проекта (публичный репозиторий)

  Даже если репозиторий публичный — следующие данные НИКОГДА не должны попасть в код:

  ### 🛡️ Защита лицензионной системы
  - `LICENSE_API_URL` и `LICENSE_VERIFY_URL` — только через ENV переменные, никакого fallback
  - IP-адрес лицензионного сервера — НИКОГДА в коде (ни как строка, ни как комментарий, ни в документации)
  - `JWT_SECRET` — только ENV, никакого дефолтного значения
  - `HWID_SALT` — только ENV, никакого fallback-значения
  - Формат ключа лицензии (структура групп, длина) — не описывать в публичном README

  ### 🛡️ Защита серверной инфраструктуры
  - IP VPS/сервера — только в `.env` файлах (в .gitignore!)
  - Логин/пароль SSH — только в secrets GitHub Actions или Vault
  - `DB_PATH` — только ENV
  - `BOT_TOKEN` — только ENV (блокировать в CI если найден)
  - `CRYPTO_BOT_TOKEN` — только ENV

  ### 🛡️ Защита бизнес-логики
  - Алгоритм генерации HWID нельзя описывать детально в комментариях
  - Анти-отладочные проверки нельзя документировать в README
  - Структуру БД лицензий нельзя выкладывать в публичную документацию

  ## Шаг 1 — Автоматическое сканирование

  ```bash
  # Критичные секреты
  rg --no-heading -n \
    -e 'ghp_[A-Za-z0-9]{36}' \
    -e 'github_pat_[A-Za-z0-9_]{82}' \
    -e '[0-9]{8,12}:[A-Za-z0-9_-]{35}' \
    -e 'sk-[A-Za-z0-9]{48}' \
    -e 'sk-proj-[A-Za-z0-9_-]+' \
    -e 'AKIA[0-9A-Z]{16}' \
    -e '-----BEGIN.*(RSA |EC |OPENSSH )?PRIVATE KEY-----' \
    -e 'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}' \
    --glob '!.git' --glob '!*.pyc' --glob '!__pycache__' . 2>/dev/null

  # Поиск хардкодных IP-адресов в Python (исключая localhost/any/broadcast)
  rg --no-heading -n \
    -e '"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"' \
    -e "'.\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'" \
    --glob '*.py' --glob '!.git' . 2>/dev/null \
    | grep -v '127\.0\.0\.' | grep -v '0\.0\.0\.0' | grep -v '255\.' | grep -v '127\.0\.1\.'

  # URL лицензионного сервера захардкожены?
  rg --no-heading -n \
    -e 'LICENSE_API_URL\s*=\s*["\''][^os\.environ]' \
    -e 'LICENSE_VERIFY_URL\s*=\s*["\''][^os\.environ]' \
    -e '_DEFAULT_LICENSE_HOST' \
    --glob '*.py' . 2>/dev/null

  # Пароли и токены
  rg --no-heading -n \
    -e 'password\s*=\s*["\''][^"\']{6,}["\'']' \
    -e 'passwd\s*=\s*["\''][^"\']{6,}["\'']' \
    -e 'secret\s*=\s*["\''][^"\']{6,}["\'']' \
    -e 'token\s*=\s*["\''][A-Za-z0-9_\-\.]{20,}["\'']' \
    --glob '*.py' --glob '!.git' . 2>/dev/null

  # SSH credentials в любых файлах
  rg --no-heading -n \
    -e 'root@\d+\.\d+\.\d+\.\d+' \
    -e 'ssh.*password' \
    --glob '!.git' . 2>/dev/null
  ```

  ## Шаг 2 — Проверка ENV-only паттерна

  Каждый чувствительный параметр должен использовать шаблон:
  ```python
  # ✅ Правильно
  VALUE = os.environ.get("KEY", "")  # без fallback значения!
  # Ещё лучше — fail fast:
  def _require_env(key):
      val = os.environ.get(key, "").strip()
      if not val: sys.exit(f"FATAL: {key} not set")
      return val
  VALUE = _require_env("KEY")

  # ❌ ЗАПРЕЩЕНО
  VALUE = os.environ.get("KEY", "https://31.76.100.190:8000")  # hardcoded fallback
  VALUE = "secret_value"  # полностью хардкод
  ```

  ## Шаг 3 — Проверка .gitignore

  ```gitignore
  # Обязательно в .gitignore:
  .env
  *.env
  *.pem
  *.key
  *.p12
  *.pfx
  *.dat         # license.dat
  *.db          # licenses.db
  fsm_storage.json
  server/.env
  credentials.json
  hwid.dat
  ```

  ## Шаг 4 — Проверка GitHub Secrets (не в коде!)

  Все эти значения должны быть ТОЛЬКО в GitHub Secrets или .env (в .gitignore):
  - `BOT_TOKEN`
  - `CRYPTO_BOT_TOKEN`
  - `JWT_SECRET`
  - `HWID_SALT`
  - `LICENSE_API_URL`
  - `LICENSE_VERIFY_URL`
  - `LICENSE_SSL_VERIFY`
  - `ADMIN_IDS`
  - `OPENAI_API_KEY`

  ## Шаг 5 — Автоматическая блокировка в CI

  Добавь в .github/workflows/secret-scan.yml проверку на IP и URL лицензии:

  ```yaml
  - name: Scan for hardcoded IPs and license URLs
    shell: bash
    run: |
      FAILED=0
      # Ищем хардкодные IP в Python файлах
      FOUND=$(grep -rE '"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}"' \
        --include="*.py" --exclude-dir=.git --exclude-dir=__pycache__ . 2>/dev/null \
        | grep -v '127.0.0' | grep -v '0.0.0.0' | grep -v '255.' || true)
      if [ -n "$FOUND" ]; then
        echo "CRITICAL: Hardcoded IP found in Python files:"; echo "$FOUND"; FAILED=1
      fi
      # Ищем хардкодные URL лицензии
      FOUND2=$(grep -rE '_DEFAULT_LICENSE_HOST|LICENSE_API_URL\s*=\s*"https?://' \
        --include="*.py" . 2>/dev/null || true)
      if [ -n "$FOUND2" ]; then
        echo "CRITICAL: Hardcoded license URL found:"; echo "$FOUND2"; FAILED=1
      fi
      [ $FAILED -eq 1 ] && exit 1 || echo "IP/URL scan passed"
  ```

  ## Реакция на находку

  1. **GitHub Token / Telegram Token** → немедленно отозвать в настройках аккаунта
  2. **IP сервера** → сменить IP VPS или закрыть порт на фаерволе
  3. **JWT_SECRET / HWID_SALT утечка** → сменить значение + аннулировать все лицензии
  4. **SSH пароль** → сменить пароль немедленно, проверить логи подключений

  ## Автоматизация

  Добавь в pre-commit hook (`.git/hooks/pre-commit`):
  ```bash
  #!/bin/bash
  python .agents/skills/secret-guard/pre_commit_check.py || exit 1
  ```
  
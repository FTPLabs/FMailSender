---
name: secret-guard
description: Сканирует Python-файлы и весь репозиторий на утечку секретов перед пушем или сборкой .exe. Обнаруживает IP-адреса, токены, пароли, ключи API, приватные ключи. Активируй ОБЯЗАТЕЛЬНО перед любым git push, созданием релиза или сборкой PyInstaller.
---

# Secret Guard — Сканер Утечки Секретов

## Когда использовать

- **ОБЯЗАТЕЛЬНО** перед каждым `git push` или `git commit`
- Перед сборкой `.exe` через PyInstaller / GitHub Actions
- При добавлении нового кода, работающего с API, базами данных, сетью
- При ревью Pull Request от внешних контрибьюторов
- Когда пользователь сообщает: "токен утёк", "пароль попал в репо", "credentials в коде"

## Что ищем

### 🔴 Критично — БЛОКИРУЕМ push
| Тип               | Пример паттерна                                |
|-------------------|------------------------------------------------|
| GitHub токены     | `ghp_[A-Za-z0-9]{36}`, `github_pat_...`        |
| Telegram токены   | `\d{8,12}:[A-Za-z0-9_-]{35}`                  |
| OpenAI API ключи  | `sk-[A-Za-z0-9]{48}`, `sk-proj-...`            |
| AWS ключи         | `AKIA[0-9A-Z]{16}`                             |
| Приватные ключи   | `-----BEGIN.*PRIVATE KEY-----`                 |
| Пароли в коде     | `password\s*=\s*["'][^"']{6,}["']`             |
| Hardcoded IP      | `\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b` в строках кода |
| JWT токены        | `eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+` |

### 🟡 Предупреждение — требует ревью
| Тип               | Пример                                         |
|-------------------|------------------------------------------------|
| IP в конфиге      | IP-адрес как дефолтное значение ENV            |
| `verify=False`    | SSL проверка отключена без комментария         |
| Чувствит. файлы   | `*.env`, `*.pem`, `*.key`, `*.p12`             |
| `TODO: remove`    | Временный хардкод, который забыли убрать       |

## Шаг 1 — Автоматическое сканирование через ripgrep

```bash
# Установить gitleaks (если не установлен)
# https://github.com/gitleaks/gitleaks

# Запуск через встроенные паттерны
rg --no-heading -n \
  -e 'ghp_[A-Za-z0-9]{36}' \
  -e 'github_pat_[A-Za-z0-9_]{82}' \
  -e '[0-9]{8,12}:[A-Za-z0-9_-]{35}' \
  -e 'sk-[A-Za-z0-9]{48}' \
  -e 'sk-proj-[A-Za-z0-9_-]+' \
  -e 'AKIA[0-9A-Z]{16}' \
  -e '-----BEGIN.*(RSA |EC |OPENSSH )?PRIVATE KEY-----' \
  -e 'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}' \
  --glob '!.git' \
  --glob '!*.pyc' \
  --glob '!__pycache__' \
  . 2>/dev/null

# Поиск хардкодных паролей в Python
rg --no-heading -n \
  -e 'password\s*=\s*["\x27][^"\x27]{6,}["\x27]' \
  -e 'passwd\s*=\s*["\x27][^"\x27]{6,}["\x27]' \
  -e 'secret\s*=\s*["\x27][^"\x27]{6,}["\x27]' \
  -e 'token\s*=\s*["\x27][A-Za-z0-9_\-\.]{20,}["\x27]' \
  --glob '*.py' \
  --glob '!.git' \
  . 2>/dev/null

# Поиск IP-адресов в Python-коде (исключая localhost и документацию)
rg --no-heading -n \
  -e '["x27]\s*\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}' \
  --glob '*.py' \
  --glob '!.git' \
  . 2>/dev/null | grep -v '127\.0\.0\.' | grep -v '0\.0\.0\.0' | grep -v '255\.'

# Проверка случайных файлов с credentials
find . -name "*.env" -o -name "*.pem" -o -name "*.key" -o -name "*.p12" \
  -o -name "*.pfx" -o -name "credentials.json" -o -name "service-account*.json" \
  2>/dev/null | grep -v ".git"
```

## Шаг 2 — Проверка .gitignore

Убедитесь что эти паттерны есть в `.gitignore`:

```gitignore
# Секреты и credentials
.env
.env.*
*.env
*.pem
*.key
*.p12
*.pfx
credentials.json
service-account*.json
*_credentials.json
secrets/
config/secrets/

# Временные файлы с данными пользователей
*_export_*.txt
*_credentials_*.txt
FmailSender_*.txt
```

## Шаг 3 — Если найдены секреты

### Немедленные действия:
1. **НЕ ПУШИТЬ** код с секретами
2. **Отозвать** скомпрометированные токены/ключи НЕМЕДЛЕННО:
   - GitHub токен: Settings → Developer settings → Personal access tokens → Revoke
   - Telegram токен: @BotFather → `/mybots` → API Token → Revoke
   - OpenAI ключ: platform.openai.com → API keys → Delete
3. **Удалить** файл из истории git:
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch путь/к/файлу" \
     --prune-empty --tag-name-filter cat -- --all
   git push origin --force --all
   ```
4. **Использовать ENV переменные** вместо хардкода:
   ```python
   # ❌ Плохо
   API_KEY = "sk-abc123..."
   
   # ✅ Хорошо
   import os
   API_KEY = os.environ.get("OPENAI_API_KEY")
   if not API_KEY:
       raise RuntimeError("OPENAI_API_KEY env var is required")
   ```

## Шаг 4 — Замена хардкодных значений

### IP-адрес сервера:
```python
# ❌ Плохо — IP захардкожен
LICENSE_URL = "https://31.76.100.190:8000/v1/activate"

# ✅ Хорошо — через ENV с обязательной проверкой
import os
_raw = os.environ.get("LICENSE_API_URL", "").strip()
if not _raw:
    raise RuntimeError(
        "LICENSE_API_URL env var is required.\n"
        "Set it in .env or export before running."
    )
LICENSE_URL = _raw
```

### Пароли и токены:
```python
# Используйте dotenv для локальной разработки
from dotenv import load_dotenv
load_dotenv()  # читает .env (не в git!)

DB_PASSWORD = os.environ["DB_PASSWORD"]   # KeyError если не задан — явная ошибка
BOT_TOKEN = os.environ.get("BOT_TOKEN")   # None если не задан — тихая ошибка
```

## Шаг 5 — Интеграция в CI (GitHub Actions)

Добавьте в `.github/workflows/secret-scan.yml` (уже создан для этого репо):

```yaml
- name: Secret scan
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Или используйте встроенный скрипт из `secret-scan.yml`.

## Связанные компоненты

- `.github/workflows/secret-scan.yml` — автосканирование в CI
- `.github/workflows/build.yml` — шаг `Secret scan before build`  
- `core/license.py` — правильное использование ENV для LICENSE_API_URL
- `server/config.py` — правильное использование ENV для BOT_TOKEN, JWT_SECRET

## Исторический контекст

⚠️ В июне 2026 года в репозиторий был случайно закоммичен файл с credentials:
- GitHub PAT token (`ghp_b0q7lv8...`) — **отозван, замените на новый**
- VPS root password и IP-адрес — **смените root пароль на VPS**
- Telegram bot tokens — **отзовите через @BotFather**

Все эти credentials скомпрометированы и не должны использоваться.

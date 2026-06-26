# FMailSender — Архитектура v6.0 (Tauri + Python)

  ## Обзор

  ```
  FMailSender/
  ├── src-tauri/          # Rust (Tauri shell)
  │   ├── src/main.rs     # Точка входа: запускает Python core, открывает WebView
  │   ├── Cargo.toml      # Rust зависимости
  │   └── tauri.conf.json # Конфиг окна, sidecar, permissions
  │
  ├── ui/                 # React + Vite фронтенд
  │   ├── src/
  │   │   ├── api.ts      # HTTP клиент → Python core (ВСЕ запросы к бэкенду здесь)
  │   │   ├── App.tsx     # Роутер, Layout wrapper
  │   │   ├── theme.ts    # Цвета, типографика (единственный источник правды)
  │   │   ├── components/
  │   │   │   └── Layout.tsx   # Sidebar + main area
  │   │   └── pages/
  │   │       ├── Dashboard.tsx   # Статистика, последняя активность
  │   │       ├── Accounts.tsx    # Управление SMTP аккаунтами
  │   │       ├── Recipients.tsx  # Список получателей
  │   │       ├── Compose.tsx     # Редактор письма
  │   │       ├── Sending.tsx     # Управление рассылкой
  │   │       └── Inbox.tsx       # Входящие / bounce
  │   ├── index.html
  │   ├── package.json
  │   └── vite.config.ts
  │
  ├── core/               # Python FastAPI сервер (HTTP API на localhost:7531)
  │   ├── server.py       # FastAPI routes — ВСЕ эндпоинты здесь
  │   ├── models.py       # Pydantic + dataclass модели (SmtpAccount, Campaign...)
  │   ├── sender.py       # SMTP движок (SendingEngine, test_smtp_connection)
  │   ├── validator.py    # SMTP + прокси валидация
  │   ├── storage.py      # Чтение/запись accounts.json, proxies.json, recipients
  │   └── proxy.py        # ProxyManager: parse, rotate, check
  │
  ├── main.py             # Точка входа: запускает core/server.py
  ├── requirements.txt    # Зависимости Python
  └── ARCHITECTURE.md     # Этот файл
  ```

  ## Как всё связано

  ```
  [Tauri main.rs]
    → spawn: python main.py (core/server.py на :7531)
    → WebView2 → http://localhost:5173 (dev) / встроенный dist/ (prod)

  [React UI] → fetch("http://localhost:7531/api/...")
  [core/server.py] → импортирует sender.py, validator.py, storage.py, proxy.py
  ```

  ## Правила для агентов

  - **Добавить эндпоинт**: только `core/server.py`
  - **Изменить хранилище**: только `core/storage.py`
  - **Изменить SMTP логику**: только `core/sender.py`
  - **Изменить прокси**: только `core/proxy.py`
  - **Изменить UI**: только `ui/src/pages/` или `ui/src/components/`
  - **Изменить цвета**: только `ui/src/theme.ts`
  - **Добавить зависимость Python**: `requirements.txt`
  - **Добавить зависимость JS**: `ui/package.json`

  ## Порты

  | Сервис | Порт | Назначение |
  |--------|------|-----------|
  | FastAPI | 7531 | HTTP API (Python core) |
  | Vite dev | 5173 | React фронтенд (dev) |
  | Tauri | — | Встраивает dist/ в prod |

  ## Запуск для разработки

  ```bash
  # Терминал 1: Python core
  pip install -r requirements.txt
  python main.py

  # Терминал 2: React dev server
  cd ui && npm install && npm run dev

  # Терминал 3: Tauri dev (после установки Rust)
  cargo tauri dev
  ```

  ## Сборка для Windows

  ```bash
  cd ui && npm run build
  cargo tauri build
  # Результат: src-tauri/target/release/bundle/msi/FMailSender_*.msi
  ```
  
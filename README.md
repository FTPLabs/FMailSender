# Email Sender Pro

**Профессиональный настольный клиент для массовых email-рассылок**  
Python 3.11 + PyQt6 + aiosmtplib · Windows 10/11 x64

---

## Возможности

| Модуль | Функции |
|---|---|
| **Лицензирование** | HWID-привязка, JWT + Fernet шифрование, offline grace 72ч, анти-VM/отладчик |
| **SMTP-движок** | Async aiosmtplib, ротация аккаунтов (round-robin / random / weighted), авто-определение SMTP по домену |
| **GUI (7 экранов)** | Активация → Дашборд → Аккаунты → Письмо → Получатели → Рассылка → Аналитика |
| **Письмо** | Rich-text + HTML с подсветкой синтаксиса, live preview, A/B тесты, вложения |
| **Получатели** | Импорт CSV/XLSX/TXT, маппинг полей, дедупликация, валидация, управление отписками |
| **Спам-анализатор** | Score 0-100 по 10 категориям, DNS-проверка (SPF/DKIM/DMARC) |
| **Warm-up** | Gaussian-задержки, планировщик по дням (1→500 писем/день) |
| **Bounce** | IMAP DSN-парсер, hard/soft bounce, автоблеклист |
| **Аналитика** | Открытия, клики, bounces, экспорт CSV + PDF (reportlab) |
| **Сборка** | PyInstaller + Inno Setup, GitHub Actions CI |

---

## Структура проекта

```
email_sender_pro/
├── main.py                         # Точка входа
├── build.py                        # PyInstaller сборка
├── requirements.txt
├── core/
│   ├── license.py                  # HWID, активация, JWT
│   ├── sender.py                   # Async SMTP движок
│   ├── warmup.py                   # Warm-up планировщик
│   ├── bounce.py                   # IMAP / DSN bounce парсер
│   └── spam_checker.py             # Спам-анализатор
├── gui/
│   ├── app.py                      # MainWindow, Sidebar, Header
│   ├── theme.py                    # QSS stylesheet, дизайн-токены
│   ├── screens/
│   │   ├── screen_activation.py    # Экран 0: Активация
│   │   ├── screen_dashboard.py     # Экран 1: Dashboard + KPI
│   │   ├── screen_accounts.py      # Экран 2: SMTP аккаунты
│   │   ├── screen_compose.py       # Экран 3: Письмо
│   │   ├── screen_recipients.py    # Экран 4: Получатели
│   │   ├── screen_sending.py       # Экран 5: Рассылка
│   │   └── screen_analytics.py     # Экран 6: Аналитика
│   └── widgets/
├── assets/
│   ├── icons/                      # app.ico (добавить вручную)
│   └── fonts/                      # Inter TTF (добавить вручную)
├── data/
│   ├── spam_words.json             # База спам-слов
│   ├── accounts.json               # SMTP аккаунты (runtime)
│   ├── recipients/                 # Списки получателей
│   ├── templates/                  # Шаблоны писем
│   ├── unsubscribe.json            # Список отписок
│   └── analytics.json              # История кампаний
├── i18n/
│   ├── ru_RU.ts                    # Русский
│   └── en_US.ts                    # Английский
├── installer/
│   └── setup.iss                   # Inno Setup скрипт
└── .github/workflows/
    └── build.yml                   # GitHub Actions CI
```

---

## Быстрый старт (разработка)

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

> **Примечание для Windows:** PyQt6-WebEngine требует Visual C++ Redistributable

### 2. Запуск

```bash
cd email_sender_pro
python main.py
```

### 3. Активация (разработка)

При первом запуске откроется экран активации.  
Для обхода в dev-режиме установите переменную окружения:
```bash
set ESP_DEV_BYPASS=1
```

---

## Сборка .exe

### Локально (Windows)

```bash
cd email_sender_pro

# Папка + все зависимости (рекомендуется)
python build.py

# Один .exe файл (больше размер, медленнее старт)
python build.py --onefile

# Очистить кэш сборки
python build.py --clean
```

### Через GitHub Actions (рекомендуется)

1. Push тег `v1.0.0` → автоматически запустится сборка  
2. Или запустите вручную: Actions → **Build EmailSenderPro Windows .exe** → Run workflow

Артефакты доступны в разделе **Actions → Artifacts** и **Releases**.

---

## Иконка приложения

Создайте `assets/icons/app.ico` (ICO, 256x256px + мультиразмер).  
Онлайн-конвертер: https://convertico.com/

---

## Шрифт Inter

1. Скачайте Inter: https://rsms.me/inter/#download
2. Распакуйте TTF файлы в `assets/fonts/`
3. Минимум: `Inter-Regular.ttf`, `Inter-Medium.ttf`, `Inter-Bold.ttf`

Если шрифт не найден — GUI автоматически переключится на Segoe UI.

---

## Конфигурация лицензирования

Файл `core/license.py`, константы:

```python
LICENSE_API_URL = "https://api.emailsenderpro.io/v1/activate"  # Ваш сервер
HWID_SALT = "..."   # Уникальная соль (сменить перед production!)
OFFLINE_GRACE_HOURS = 72
```

### Форматы лицензионных ключей

```
ESP-XXXXX-XXXXX-XXXXX-XXXXX
```

Пример: `ESP-A1B2C-D3E4F-G5H6I-J7K8L`

### Планы

| Параметр | STARTER | PRO | UNLIMITED |
|---|---|---|---|
| Писем в день | 1 000 | 50 000 | Без лимита |
| Потоков | 5 | 25 | 50 |
| A/B вариантов | 2 | 5 | 10 |
| Warm-up | — | ✓ | ✓ |

---

## Сервер лицензий (ваш backend)

Endpoint `POST /v1/activate`:

**Request:**
```json
{
  "key": "ESP-A1B2C-D3E4F-G5H6I-J7K8L",
  "hwid": "sha256-fingerprint",
  "version": "1.0.0",
  "os": "Windows-11-10.0.22631"
}
```

**Response (success):**
```json
{
  "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "plan": "PRO",
  "expires_at": "2025-12-31T00:00:00Z",
  "max_daily": 50000,
  "max_threads": 25
}
```

---

## Данные пользователя

| Файл | Содержимое |
|---|---|
| `%APPDATA%\EmailSenderPro\license.dat` | Зашифрованная лицензия (Fernet + HWID) |
| `data/accounts.json` | SMTP аккаунты |
| `data/unsubscribe.json` | Список отписавшихся |
| `data/analytics.json` | История кампаний |
| `data/templates/` | Шаблоны писем (JSON) |

---

## Стек технологий

| Компонент | Технология | Версия |
|---|---|---|
| GUI фреймворк | PyQt6 | ≥ 6.6.0 |
| Email preview | PyQt6-WebEngine | ≥ 6.6.0 |
| SMTP отправка | aiosmtplib | ≥ 3.0.0 |
| Шифрование | cryptography (Fernet, RSA) | ≥ 41.0.0 |
| JWT лицензии | PyJWT | ≥ 2.8.0 |
| DNS проверки | dnspython | ≥ 2.4.0 |
| Excel импорт | openpyxl | ≥ 3.1.2 |
| PDF экспорт | reportlab | ≥ 4.0.0 |
| Сборка | PyInstaller | ≥ 6.0.0 |
| Установщик | Inno Setup 6 | ≥ 6.2.0 |
| CI/CD | GitHub Actions | — |

---

## Лицензия

Проприетарное ПО. Все права защищены.

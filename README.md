# FMailSender

Профессиональный инструмент для массовых email-рассылок.

## Архитектура (v7)

```
FMailSender.exe  ← один portable EXE, без установщика
  └── Tauri v2 (WebView2 shell)
        ├── Python FastAPI ядро (fmail-core, встроен внутрь EXE)
        │     └── core/ — SMTP движок, лицензия, прокси, DKIM...
        └── React/Vite UI (встроен в bundle)
```

**Запуск:** скачал → запустил → приложение открылось. Установщик не нужен.

## Возможности

- Рассылки до **10-15к+ писем** с оптимизированным пулом соединений
- SMTP Connection Pool — 5-10x быстрее стандартной отправки
- Чекпоинты кампаний — resume при перезапуске/крэше
- SOCKS5/HTTP прокси для всех соединений (защита IP)
- OAuth2/XOAUTH2 для Microsoft (Outlook/Hotmail)
- 300+ SMTP-провайдеров предварительно настроены
- Уникализация писем (spintax, CSS fingerprint)
- IMAP bounce-монитор + автоматический blacklist
- Прогрев аккаунтов (warmup scheduler)
- Спам-скор проверка

## Системные требования

- Windows 10/11 x64
- WebView2 Runtime (предустановлен в Windows 11)
- 512 МБ свободной памяти

## Установка

1. Скачайте **FMailSender_vX.X.X.exe** из [Releases](https://github.com/FTPLabs/FMailSender/releases)
2. Запустите — окно откроется сразу (установщик не нужен)
3. При **первом** запуске Windows Defender проверяет файлы Python ядра (20–90 сек) — это нормально
4. Для мгновенного старта добавьте `%LOCALAPPDATA%\FMailSender` в исключения антивируса

## Разработка

```bash
# Терминал 1: Python core
pip install -r requirements.txt
python main.py

# Терминал 2: React UI
cd ui && npm install && npm run dev
```

## Сборка релиза (CI)

Сборка и деплой запускаются автоматически при создании тега:

```bash
git tag v7.0.2 && git push origin v7.0.2
```

Результат: `FMailSender_v7.0.2.exe` — portable EXE, ~28 МБ, без установщика.

## Лицензия

Платный продукт. Активация на сайте [fmail.shop](https://fmail.shop/)

---
  name: proxy-smtp-requirements
  description: Требования к прокси для SMTP-соединений в FMailSender. Активируй когда аккаунты показывают PROXY_BLOCKED_SMTP, CONN_ERROR после перебора всех портов, или пользователь жалуется что все аккаунты невалидны через прокси.
  ---

  # Proxy SMTP Requirements

  ## TL;DR

  **Не каждый SOCKS5 прокси поддерживает SMTP.** FoxyProxy, большинство datacenter-прокси блокируют порты 465/587/25 (anti-spam). Нужен residential или SMTP-dedicated прокси.

  ## Коды ошибок

  | Код | Причина | Действие |
  |-----|---------|----------|
  | PROXY_BLOCKED_SMTP | Прокси блокирует SMTP-порты (SOCKS5 General Failure code 1) | Смените прокси |
  | CONN_ERROR | Прокси блокирует хост или хост недоступен | Проверьте прокси и хост |
  | AUTH_FAIL (535) | Неверный пароль или SMTP отключён | Проверьте пароль / включите SMTP в настройках |

  ## Проверка поддержки SMTP прокси

  ```bash
  curl --proxy socks5h://user:pass@proxy-host:port smtp://smtp.gmx.com:465 --connect-timeout 10
  # "220 ..." = работает | "cannot complete SOCKS5 (1)" = блокирует
  ```

  ## Провайдеры

  **Работают:** Bright Data, Oxylabs, Smartproxy, SSH-туннель (ssh -D 1080)

  **Блокируют:** FoxyProxy (gw.foxyproxy.online), HideMyAss, NordVPN, большинство VPN-прокси

  ## SSH SOCKS5 (бесплатно с VPS)

  ```bash
  ssh -N -D 1080 -o ServerAliveInterval=60 root@your-vps-ip
  # Прокси для FMailSender: socks5://127.0.0.1:1080
  ```

  ## GMX 535 AUTH FAIL

  1. Войти в GMX → Email → Settings → POP3 & IMAP → включить SMTP
  2. Если есть 2FA → создать App Password

  ## Диагностика из тестов (2026-06-22)

  - Rambler (smtp.rambler.ru:465): **100%** аккаунтов OK при прямом подключении
  - GMX (smtp.gmx.com:465): **~60%** OK; ~40% — AUTH 535
  
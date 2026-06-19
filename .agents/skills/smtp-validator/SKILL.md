---
  name: smtp-validator
  description: Полная проверка SMTP-соединений и DNS-конфигурации для всех аккаунтов FMailSender. Активируй при добавлении нового аккаунта, ошибках авторизации, проблемах с доставкой, или когда пользователь говорит "не отправляется", "SMTP не работает", "проверь соединение".
  ---

  # SMTP Validator — Полная диагностика подключений

  ## Что проверяет core/smtp_validator.py

  ```
  TCP → EHLO → AUTH → STARTTLS/SSL → DNS (MX, SPF, DKIM, DMARC) → DNSBL (blacklist)
  ```

  ## Запуск диагностики

  ```python
  from core.smtp_validator import SmtpValidator

  validator = SmtpValidator()
  # Проверить один аккаунт
  result = validator.validate_account("user@gmail.com", "password", callback=print)

  # Проверить все аккаунты из списка
  results = validator.validate_all(accounts_list, on_result=callback, on_done=done_cb)
  ```

  ## Коды результатов

  | Код | Значение | Действие |
  |-----|---------|---------|
  | OK | Соединение успешно | Можно отправлять |
  | AUTH_FAIL | Неверный логин/пароль | Проверить учётные данные |
  | SSL_ERROR | Проблема с сертификатом | Попробовать другой порт/режим |
  | TIMEOUT | Сервер не отвечает | Проверить брандмауэр |
  | BLACKLISTED | IP в DNSBL | Сменить IP или почистить репутацию |
  | SPF_FAIL | SPF запись не настроена | Добавить SPF на домен отправителя |
  | MX_FAIL | MX запись не найдена | Проблема с DNS получателя |

  ## DNS-проверки для домена отправителя

  ```bash
  # SPF
  dig TXT yourdomain.com | grep "v=spf1"

  # DKIM (selector default)
  dig TXT default._domainkey.yourdomain.com

  # DMARC
  dig TXT _dmarc.yourdomain.com
  ```

  ## Чеклист при добавлении нового SMTP аккаунта

  - [ ] Порт 465 (SSL) или 587 (TLS/STARTTLS) — не 25 (блокируется провайдерами)
  - [ ] App password вместо основного пароля (Gmail, Yahoo, Outlook)
  - [ ] SPF запись включает IP или домен сервера отправки
  - [ ] Аккаунт не в DNSBL: mxtoolbox.com/blacklists.aspx
  - [ ] Тест через validator.validate_account() до добавления в пул

  ## Авто-определение конфига по домену

  ```python
  from core.sender import get_smtp_config
  config = get_smtp_config("user@newdomain.com")
  # Если домен неизвестен → fallback: MX lookup → автоконфиг
  ```
  
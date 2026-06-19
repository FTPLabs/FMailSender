---
  name: smtp-configs-extended
  description: Расширенный справочник SMTP-конфигураций. Активируй при добавлении нового email-провайдера в _SMTP_CONFIGS (core/sender.py), или когда пользователь говорит "добавь поддержку [провайдер]", "не определяется домен", "нужен кастомный SMTP".
  ---

  # SMTP Configs Extended — core/sender.py

  ## Как добавить нового провайдера

  ```python
  # В _SMTP_CONFIGS dict:
  "newdomain.com": {"host": "smtp.newdomain.com", "port": 465, "use_ssl": True, "use_tls": False},
  # С IMAP поддержкой (для reply-monitor):
  "newdomain.com": {"host": "smtp.newdomain.com", "port": 465, "use_ssl": True, "use_tls": False,
                     "imap_host": "imap.newdomain.com", "imap_port": 993, "imap_ssl": True},
  ```

  ## Провайдеры добавленные в v3.5.0 (см. core/smtp_configs_extra.py)

  ### Transactional / Marketing SMTP
  | Провайдер | Host | Port | SSL |
  |-----------|------|------|-----|
  | SendGrid | smtp.sendgrid.net | 587 | TLS |
  | Mailgun | smtp.mailgun.org | 587 | TLS |
  | Amazon SES (EU) | email-smtp.eu-west-1.amazonaws.com | 465 | SSL |
  | Amazon SES (US) | email-smtp.us-east-1.amazonaws.com | 465 | SSL |
  | Postmark | smtp.postmarkapp.com | 587 | TLS |
  | SparkPost | smtp.sparkpostmail.com | 587 | TLS |
  | Brevo (Sendinblue) | smtp-relay.brevo.com | 587 | TLS |

  ### ProtonMail Bridge (локальный)
  ```python
  "protonmail.com": {"host": "127.0.0.1", "port": 1025, "use_ssl": False, "use_tls": False,
                      "_note": "Требует ProtonMail Bridge приложение"},
  ```

  ### Fastmail
  ```python
  "fastmail.com": {"host": "smtp.fastmail.com", "port": 465, "use_ssl": True, "use_tls": False},
  "fastmail.fm":  {"host": "smtp.fastmail.com", "port": 465, "use_ssl": True, "use_tls": False},
  ```

  ### Азиатские провайдеры
  | Домен | Host | Port |
  |-------|------|------|
  | qq.com | smtp.qq.com | 465 |
  | 163.com | smtp.163.com | 465 |
  | 126.com | smtp.126.com | 465 |
  | sina.com | smtp.sina.com | 465 |
  | naver.com | smtp.naver.com | 587 |

  ### Fallback: MX Lookup
  ```python
  # Если домен не в _SMTP_CONFIGS — ищем MX запись
  import dns.resolver
  mx = dns.resolver.resolve(domain, "MX")
  host = str(sorted(mx, key=lambda r: r.preference)[0].exchange).rstrip(".")
  # Пробуем port 465 SSL, потом 587 TLS, потом 25
  ```

  ## Правило добавления новой записи

  1. Проверить реальный host через `mxtoolbox.com/smtp`
  2. Добавить в `core/smtp_configs_extra.py` (не в sender.py напрямую)
  3. sender.py при старте делает `_SMTP_CONFIGS.update(load_extra_configs())`
  4. Запустить `smtp_validator.validate_account()` для проверки
  
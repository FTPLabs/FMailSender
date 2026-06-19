---
  name: reply-monitor
  description: Мониторинг ответов получателей через IMAP. Активируй при добавлении функции ответов, изменении core/reply_monitor.py, или когда пользователь говорит "ответы получателей", "входящие", "reply", "хочу видеть ответы", "диалог с получателем".
  ---

  # Reply Monitor — Мониторинг ответов получателей

  ## Архитектура core/reply_monitor.py

  ```
  ReplyMonitor (threading.Thread, daemon=True)
    ↓ IMAP IDLE / polling каждые 30 сек
    ↓ Фильтрует bounce-сообщения (уже в bounce.py)
    ↓ Определяет настоящие ответы по Message-ID / In-Reply-To
    ↓ pyqtSignal → GUI (screen_inbox.py)
  ```

  ## Определение "настоящего ответа" (не bounce)

  ```python
  def is_real_reply(msg: email.message.Message, sent_message_ids: set) -> bool:
      in_reply_to = msg.get("In-Reply-To", "")
      references  = msg.get("References", "")
      # Ответ если: In-Reply-To совпадает с Message-ID отправленного письма
      return any(mid in in_reply_to or mid in references for mid in sent_message_ids)
  ```

  ## Интеграция с GUI (screen_inbox.py)

  ```python
  # Сигналы
  reply_received = pyqtSignal(dict)    # {"from": "...", "subject": "...", "body": "...", "msg_id": "..."}
  reply_count_changed = pyqtSignal(int)  # количество непрочитанных

  # Отправить ответ
  def send_reply(self, original_msg: dict, reply_text: str):
      # Формирует Re: subject + In-Reply-To header
      # Использует тот же SMTP аккаунт что отправил оригинал
  ```

  ## IMAP соединение

  ```python
  # Конфигурация IMAP из _SMTP_CONFIGS (поле imap_host/imap_port/imap_ssl)
  # Если imap_host не задан — пытаемся угадать: imap.{domain}:993
  imap = imaplib.IMAP4_SSL(imap_host, imap_port)
  imap.login(username, password)
  imap.select("INBOX")

  # Поиск непрочитанных ответов на наши письма
  _, ids = imap.search(None, "UNSEEN")
  ```

  ## Хранение трекинга Message-ID

  ```python
  # Сохраняем Message-ID каждого отправленного письма
  # Файл: {data_dir}/sent_message_ids.json
  # Формат: {"campaign_id": ["<msg-id-1>", "<msg-id-2>"], ...}
  ```

  ## Чеклист при добавлении экрана Inbox

  - [ ] ReplyMonitor запускается при старте app (не при открытии экрана)
  - [ ] Один монитор на аккаунт (не создавать каждый раз новый)
  - [ ] Уведомление в sidebar (badge с числом непрочитанных)
  - [ ] При ответе — формировать правильные заголовки In-Reply-To и References
  - [ ] IMAP credentials — те же что для SMTP (из AccountConfig)
  
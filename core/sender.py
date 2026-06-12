"""
  FMailSender core sending engine v2.7.0.
  Fixes: thread-safe can_send (full lock), asyncio.get_running_loop(),
         real async parallelism via gather, _hour_reset typo corrected.
  """
  from __future__ import annotations

  import asyncio
  import mimetypes
  import queue
  import random
  import re
  import smtplib
  import threading
  import time
  import uuid
  from dataclasses import dataclass, field
  from email.mime.application import MIMEApplication
  from email.mime.multipart import MIMEMultipart
  from email.mime.text import MIMEText
  from pathlib import Path
  from typing import Callable, List, Optional

  try:
      import aiosmtplib
      _HAS_AIOSMTPLIB = True
  except ImportError:
      _HAS_AIOSMTPLIB = False


  _SMTP_CONFIGS: dict[str, dict] = {
      "gmail.com":       {"host": "smtp.gmail.com",       "port": 465, "use_ssl": True,  "use_tls": False},
      "googlemail.com":  {"host": "smtp.gmail.com",       "port": 465, "use_ssl": True,  "use_tls": False},
      "outlook.com":     {"host": "smtp.office365.com",   "port": 587, "use_ssl": False, "use_tls": True},
      "hotmail.com":     {"host": "smtp.office365.com",   "port": 587, "use_ssl": False, "use_tls": True},
      "live.com":        {"host": "smtp.office365.com",   "port": 587, "use_ssl": False, "use_tls": True},
      "msn.com":         {"host": "smtp.office365.com",   "port": 587, "use_ssl": False, "use_tls": True},
      "yahoo.com":       {"host": "smtp.mail.yahoo.com",  "port": 465, "use_ssl": True,  "use_tls": False},
      "yahoo.co.uk":     {"host": "smtp.mail.yahoo.com",  "port": 465, "use_ssl": True,  "use_tls": False},
      "ymail.com":       {"host": "smtp.mail.yahoo.com",  "port": 465, "use_ssl": True,  "use_tls": False},
      "mail.ru":         {"host": "smtp.mail.ru",         "port": 465, "use_ssl": True,  "use_tls": False},
      "inbox.ru":        {"host": "smtp.mail.ru",         "port": 465, "use_ssl": True,  "use_tls": False},
      "list.ru":         {"host": "smtp.mail.ru",         "port": 465, "use_ssl": True,  "use_tls": False},
      "bk.ru":           {"host": "smtp.mail.ru",         "port": 465, "use_ssl": True,  "use_tls": False},
      "yandex.ru":       {"host": "smtp.yandex.ru",       "port": 465, "use_ssl": True,  "use_tls": False},
      "yandex.com":      {"host": "smtp.yandex.com",      "port": 465, "use_ssl": True,  "use_tls": False},
      "ya.ru":           {"host": "smtp.yandex.ru",       "port": 465, "use_ssl": True,  "use_tls": False},
      "icloud.com":      {"host": "smtp.mail.me.com",     "port": 587, "use_ssl": False, "use_tls": True},
      "me.com":          {"host": "smtp.mail.me.com",     "port": 587, "use_ssl": False, "use_tls": True},
      "mac.com":         {"host": "smtp.mail.me.com",     "port": 587, "use_ssl": False, "use_tls": True},
      "gmx.com":         {"host": "mail.gmx.com",         "port": 587, "use_ssl": False, "use_tls": True},
      "gmx.net":         {"host": "mail.gmx.net",         "port": 587, "use_ssl": False, "use_tls": True},
      "gmx.de":          {"host": "mail.gmx.net",         "port": 587, "use_ssl": False, "use_tls": True},
      "web.de":          {"host": "smtp.web.de",          "port": 587, "use_ssl": False, "use_tls": True},
      "aol.com":         {"host": "smtp.aol.com",         "port": 465, "use_ssl": True,  "use_tls": False},
      "zoho.com":        {"host": "smtp.zoho.com",        "port": 465, "use_ssl": True,  "use_tls": False},
  }


  def get_smtp_config_for_domain(domain: str) -> Optional[dict]:
      return _SMTP_CONFIGS.get(domain.lower().strip())


  @dataclass
  class SmtpAccount:
      email: str
      password: str
      host: str
      port: int = 465
      use_ssl: bool = True
      use_tls: bool = False
      display_name: str = ""
      daily_limit: int = 500
      hourly_limit: int = 50
      is_active: bool = True
      proxy: str = ""

      def __post_init__(self):
          self._lock = threading.Lock()
          self.sent_today: int = 0
          self.sent_this_hour: int = 0
          self._hour_reset: float = time.time()

      @property
      def can_send(self) -> bool:
          """Thread-safe check — entire body is protected by the lock."""
          if not self.is_active:
              return False
          with self._lock:
              now = time.time()
              if now - self._hour_reset >= 3600:
                  self.sent_this_hour = 0
                  self._hour_reset = now  # FIX: was mistakenly assigning to sent_this_hour
              return self.sent_today < self.daily_limit and self.sent_this_hour < self.hourly_limit

      def increment_sent(self) -> None:
          """Thread-safe counter increment."""
          with self._lock:
              self.sent_today += 1
              self.sent_this_hour += 1


  @dataclass
  class Recipient:
      email: str
      first_name: str = ""
      last_name: str = ""
      company: str = ""
      custom_1: str = ""
      custom_2: str = ""
      custom_3: str = ""
      custom_4: str = ""
      custom_5: str = ""


  @dataclass
  class EmailTemplate:
      subject: str
      body_html: str = ""
      body_text: str = ""
      attachments: List[str] = field(default_factory=list)
      reply_to: str = ""
      cc: List[str] = field(default_factory=list)

      def personalize(self, recipient: Recipient) -> "EmailTemplate":
          subs = {
              "{{email}}":      recipient.email,
              "{{first_name}}": recipient.first_name,
              "{{last_name}}":  recipient.last_name,
              "{{company}}":    recipient.company,
              "{{custom_1}}":   recipient.custom_1,
              "{{custom_2}}":   recipient.custom_2,
              "{{custom_3}}":   recipient.custom_3,
              "{{custom_4}}":   recipient.custom_4,
              "{{custom_5}}":   recipient.custom_5,
              "{{full_name}}":  f"{recipient.first_name} {recipient.last_name}".strip(),
          }

          def sub(text: str) -> str:
              for k, v in subs.items():
                  text = text.replace(k, v)
              return text

          return EmailTemplate(
              subject=sub(self.subject),
              body_html=sub(self.body_html),
              body_text=sub(self.body_text),
              attachments=self.attachments,
              reply_to=self.reply_to,
              cc=self.cc,
          )


  @dataclass
  class CampaignConfig:
      max_threads: int = 5
      min_delay_ms: int = 500
      max_delay_ms: int = 2000
      pause_after_n: int = 100
      pause_duration_sec: float = 60.0
      track_opens: bool = True
      track_clicks: bool = True
      unsubscribe_link: str = ""
      rotate_accounts: bool = True


  @dataclass
  class SendResult:
      recipient_email: str
      success: bool = False
      error: str = ""
      account_used: str = ""
      message_id: str = ""
      timestamp: float = field(default_factory=time.time)


  _EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


  def validate_email_format(email: str) -> bool:
      return bool(_EMAIL_RE.match(email.strip())) if email else False


  def _build_message(
      account: SmtpAccount,
      recipient: Recipient,
      template: EmailTemplate,
  ) -> MIMEMultipart:
      """Build MIME message: multipart/mixed -> multipart/alternative -> html."""
      msg_id = f"<{uuid.uuid4().hex}@{account.host}>"
      from_addr = (
          f"{account.display_name} <{account.email}>"
          if account.display_name else account.email
      )
      outer = MIMEMultipart("mixed")
      outer["Subject"] = template.subject
      outer["From"] = from_addr
      outer["To"] = recipient.email
      outer["Message-ID"] = msg_id
      outer["Date"] = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())
      if template.reply_to:
          outer["Reply-To"] = template.reply_to

      alt = MIMEMultipart("alternative")
      plain = template.body_text or re.sub(r"<[^>]+>", "", template.body_html)
      alt.attach(MIMEText(plain, "plain", "utf-8"))
      alt.attach(MIMEText(template.body_html, "html", "utf-8"))
      outer.attach(alt)

      for att_path in template.attachments:
          p = Path(att_path)
          if not p.exists():
              continue
          mime_type, _ = mimetypes.guess_type(str(p))
          main_type, sub_type = (mime_type or "application/octet-stream").split("/", 1)
          with open(p, "rb") as f:
              data = f.read()
          att = MIMEApplication(data, _subtype=sub_type)
          att.add_header("Content-Disposition", "attachment", filename=p.name)
          outer.attach(att)

      return outer


  async def test_smtp_connection(account: SmtpAccount) -> tuple[bool, str]:
      if not _HAS_AIOSMTPLIB:
          try:
              import ssl
              ctx = ssl.create_default_context()
              if account.use_ssl:
                  s = smtplib.SMTP_SSL(account.host, account.port, context=ctx, timeout=15)
              else:
                  s = smtplib.SMTP(account.host, account.port, timeout=15)
                  if account.use_tls:
                      s.starttls(context=ctx)
              s.login(account.email, account.password)
              s.quit()
              return True, f"OK — {account.host}:{account.port}"
          except Exception as e:
              return False, f"ОШИБКА: {e}"
      try:
          if account.use_ssl:
              smtp = aiosmtplib.SMTP(
                  hostname=account.host, port=account.port,
                  use_tls=True, start_tls=False, timeout=20,
              )
          else:
              smtp = aiosmtplib.SMTP(
                  hostname=account.host, port=account.port,
                  use_tls=False, start_tls=account.use_tls, timeout=20,
              )
          await smtp.connect()
          await smtp.login(account.email, account.password)
          await smtp.quit()
          return True, f"OK — SMTP {account.host}:{account.port} авторизация успешна"
      except Exception as e:
          return False, f"ОШИБКА [{type(e).__name__}]: {e}"


  class SendingEngine:
      """
      Async campaign engine.

      engine = SendingEngine(accounts, config, log_queue=q)
      engine.on_progress = lambda sent, total, result: ...
      engine.on_finished = lambda results: ...
      loop.run_until_complete(engine.run_campaign(recipients, template))

      engine.stats       -> {"success": N, "errors": N, "total": N}
      engine._paused     -> bool
      engine.pause()  /  engine.resume()  /  engine.stop()
      """

      def __init__(
          self,
          accounts: List[SmtpAccount],
          config: CampaignConfig,
          log_queue: Optional[queue.Queue] = None,
          recipients: Optional[List[Recipient]] = None,
          template: Optional[EmailTemplate] = None,
          result_queue: Optional[queue.Queue] = None,
          stop_event: Optional[threading.Event] = None,
      ):
          self.accounts = accounts
          self.config = config
          self._log_queue: Optional[queue.Queue] = log_queue or result_queue
          self._recipients: List[Recipient] = recipients or []
          self._template: Optional[EmailTemplate] = template
          self.stop_event = stop_event or threading.Event()
          self._paused = False
          self.on_progress: Optional[Callable] = None
          self.on_finished: Optional[Callable] = None
          self._stats: dict = {"success": 0, "errors": 0, "total": 0}
          self._stats_lock = threading.Lock()

      @property
      def stats(self) -> dict:
          with self._stats_lock:
              return dict(self._stats)

      def pause(self) -> None:
          self._paused = True

      def resume(self) -> None:
          self._paused = False

      def stop(self) -> None:
          self.stop_event.set()
          self._paused = False

      def run(self) -> None:
          loop = asyncio.new_event_loop()
          asyncio.set_event_loop(loop)
          try:
              tpl = self._template or EmailTemplate(subject="(no subject)", body_html="")
              loop.run_until_complete(self.run_campaign(self._recipients, tpl))
          finally:
              loop.close()

      async def run_campaign(
          self,
          recipients: List[Recipient],
          template: EmailTemplate,
      ) -> List[SendResult]:
          self._recipients = recipients
          self._template = template
          with self._stats_lock:
              self._stats = {"success": 0, "errors": 0, "total": len(recipients)}
          self.stop_event.clear()
          self._paused = False

          results: List[SendResult] = []
          sem = asyncio.Semaphore(self.config.max_threads)

          # FIX: use gather for real parallelism — create tasks in batches
          pending_tasks: list = []

          async def _process_batch(batch_recipients: List[Recipient]) -> List[SendResult]:
              tasks = []
              for recipient in batch_recipients:
                  account = self._pick_account()
                  if account is None:
                      result = SendResult(
                          recipient_email=recipient.email,
                          success=False,
                          error="Нет доступных аккаунтов",
                      )
                      with self._stats_lock:
                          self._stats["errors"] += 1
                      self._emit_progress(results, recipients, result)
                      tasks.append(asyncio.coroutine(lambda r=result: r)())
                      continue
                  delay = random.randint(self.config.min_delay_ms, self.config.max_delay_ms) / 1000.0
                  await asyncio.sleep(delay / self.config.max_threads)
                  tasks.append(self._send_one(sem, account, recipient, template))
              return await asyncio.gather(*tasks, return_exceptions=False)

          batch_size = max(self.config.max_threads, 1)
          i = 0
          while i < len(recipients):
              if self.stop_event.is_set():
                  break
              while self._paused and not self.stop_event.is_set():
                  await asyncio.sleep(0.1)
              if self.stop_event.is_set():
                  break

              if i > 0 and (i % self.config.pause_after_n) == 0:
                  await asyncio.sleep(self.config.pause_duration_sec)

              batch = recipients[i:i + batch_size]
              batch_results = await _process_batch(batch)

              for result in batch_results:
                  if isinstance(result, Exception):
                      continue
                  results.append(result)
                  with self._stats_lock:
                      if result.success:
                          self._stats["success"] += 1
                      else:
                          self._stats["errors"] += 1
                  self._emit_progress(results, recipients, result)

              i += batch_size

          if self.on_finished is not None:
              try:
                  self.on_finished(results)
              except Exception:
                  pass
          return results

      def _emit_progress(self, results, recipients, result) -> None:
          if self.on_progress is not None:
              try:
                  self.on_progress(len(results), len(recipients), result)
              except Exception:
                  pass

      def _pick_account(self) -> Optional[SmtpAccount]:
          active = [a for a in self.accounts if a.can_send]
          if not active:
              return None
          return min(active, key=lambda a: a.sent_today) if self.config.rotate_accounts else active[0]

      async def _send_one(
          self,
          sem: asyncio.Semaphore,
          account: SmtpAccount,
          recipient: Recipient,
          template: EmailTemplate,
      ) -> SendResult:
          async with sem:
              if self.stop_event.is_set():
                  return SendResult(
                      recipient_email=recipient.email,
                      success=False,
                      error="Отменено",
                      account_used=account.email,
                  )
              personalized = template.personalize(recipient)
              msg = _build_message(account, recipient, personalized)
              if not _HAS_AIOSMTPLIB:
                  # FIX: use get_running_loop() instead of deprecated get_event_loop()
                  loop = asyncio.get_running_loop()
                  return await loop.run_in_executor(None, self._send_sync, account, recipient, msg)
              try:
                  if account.use_ssl:
                      await aiosmtplib.send(
                          msg,
                          hostname=account.host, port=account.port,
                          username=account.email, password=account.password,
                          use_tls=True, start_tls=False, timeout=30,
                      )
                  else:
                      await aiosmtplib.send(
                          msg,
                          hostname=account.host, port=account.port,
                          username=account.email, password=account.password,
                          use_tls=False, start_tls=account.use_tls, timeout=30,
                      )
                  account.increment_sent()
                  return SendResult(
                      recipient_email=recipient.email,
                      success=True,
                      account_used=account.email,
                      message_id=msg.get("Message-ID", ""),
                  )
              except Exception as exc:
                  return SendResult(
                      recipient_email=recipient.email,
                      success=False,
                      error=str(exc),
                      account_used=account.email,
                  )

      def _send_sync(self, account: SmtpAccount, recipient: Recipient, msg: MIMEMultipart) -> SendResult:
          import ssl
          try:
              ctx = ssl.create_default_context()
              if account.use_ssl:
                  s = smtplib.SMTP_SSL(account.host, account.port, context=ctx, timeout=30)
              else:
                  s = smtplib.SMTP(account.host, account.port, timeout=30)
                  if account.use_tls:
                      s.starttls(context=ctx)
              s.login(account.email, account.password)
              s.sendmail(account.email, recipient.email, msg.as_string())
              s.quit()
              account.increment_sent()
              return SendResult(
                  recipient_email=recipient.email,
                  success=True,
                  account_used=account.email,
                  message_id=msg.get("Message-ID", ""),
              )
          except Exception as exc:
              return SendResult(
                  recipient_email=recipient.email,
                  success=False,
                  error=str(exc),
                  account_used=account.email,
              )
  
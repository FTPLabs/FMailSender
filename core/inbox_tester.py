"""
FMailSender Inbox Tester v2.0.0

Два режима проверки доставляемости:

1. Реальный тест размещения (Inbox vs Spam) по seed-аккаунтам через IMAP.
 Отправляем помеченное письмо на seed-адреса и опрашиваем их IMAP,
 определяя папку (Входящие / Спам) по каждому провайдеру. Это даёт
 честную матрицу размещения, а не абстрактный балл.

2. mail-tester.com — опциональная числовая оценка письма (0-10).
 Сохранено для обратной совместимости (generate_test_address / fetch_result).
"""
from __future__ import annotations

import imaplib
import random
import re
import smtplib
import ssl
import string
import time
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from typing import Callable, Optional

# Заголовок-метка, по которому ищем тестовое письмо в почте seed-аккаунта.
TEST_HEADER = "X-FMail-Test-ID"

# Имена папок «Спам/Нежелательное» по провайдерам (после флага \Junk).
_JUNK_NAMES = [
  "junk", "spam", "junk email", "junk e-mail", "bulk", "bulk mail",
  "спам", "нежелательная почта", "нежелательная",
  "[gmail]/spam", "[gmail]/спам",
  "inbox.junk", "inbox.spam",
]

# Домены Microsoft → IMAP через XOAUTH2.
_MS_DOMAINS = frozenset({
  "outlook.com", "hotmail.com", "live.com", "msn.com", "windowslive.com",
  "outlook.de", "hotmail.de", "live.de", "outlook.fr", "hotmail.fr",
  "live.fr", "outlook.ru", "hotmail.ru", "live.ru", "outlook.co.uk",
  "hotmail.co.uk", "outlook.es", "hotmail.es", "outlook.it", "hotmail.it",
})


# ════════════════════════════════════════════════════════════════════════
#  Реальный тест размещения (Inbox vs Spam) через IMAP
# ════════════════════════════════════════════════════════════════════════

def make_test_tag() -> str:
  """Уникальная метка теста (для заголовка и темы)."""
  return "".join(random.choices(string.ascii_lowercase + string.digits, k=14))


def _domain_of(email: str) -> str:
  return email.split("@", 1)[-1].lower().strip() if "@" in email else ""


def _is_ms(email: str) -> bool:
  return _domain_of(email) in _MS_DOMAINS


def _imap_host_for(account) -> tuple[str, int, bool]:
  """Определяет (host, port, ssl) для IMAP seed-аккаунта."""
  host = getattr(account, "imap_host", "") or ""
  port = int(getattr(account, "imap_port", 993) or 993)
  use_ssl = bool(getattr(account, "imap_ssl", True))
  if host:
      return host, port, use_ssl
  # Из карты провайдеров sender.py по домену
  try:
      from core.sender import get_smtp_config_for_domain
      cfg = get_smtp_config_for_domain(_domain_of(account.email)) or {}
      if cfg.get("imap_host"):
          return cfg["imap_host"], int(cfg.get("imap_port", 993)), bool(cfg.get("imap_ssl", True))
  except Exception:
      pass
  # Резерв: imap.<домен>
  dom = _domain_of(account.email)
  return (f"imap.{dom}" if dom else ""), 993, True


def _smtp_send(sender, to_addr: str, msg) -> tuple[bool, str]:
  """Отправляет письмо через SMTP sender-аккаунта (XOAUTH2 для MS, иначе LOGIN)."""
  host = getattr(sender, "host", "") or getattr(sender, "smtp_host", "")
  port = int(getattr(sender, "port", 465) or 465)
  use_ssl = bool(getattr(sender, "use_ssl", port == 465))
  use_tls = bool(getattr(sender, "use_tls", port in (587, 25)))
  user = sender.email
  pwd = getattr(sender, "password", "")

  # OAuth2-токен для Microsoft (Outlook/Hotmail/Live) — обязателен для XOAUTH2
  oauth_tok = ""
  if _is_ms(user) and (
      getattr(sender, "refresh_token", "")
      or getattr(sender, "access_token", "")
      or getattr(sender, "oauth_token", "")
  ):
      try:
          from core.oauth2_refresh import get_valid_access_token
          oauth_tok = get_valid_access_token(sender) or ""
      except Exception:
          oauth_tok = ""
      if not oauth_tok:
          return False, "OAuth2: не удалось получить access token для Microsoft-аккаунта"

  def _auth(srv) -> tuple[bool, str]:
      srv.ehlo()
      if oauth_tok:
          from core.oauth2_refresh import build_xoauth2
          xo = build_xoauth2(user, oauth_tok)
          code, resp = srv.docmd("AUTH", "XOAUTH2 " + xo)
          if code == 334:  # challenge → авторизация не прошла
              code, resp = srv.docmd("")
          if code != 235:
              rmsg = resp.decode("utf-8", "replace") if isinstance(resp, (bytes, bytearray)) else str(resp)
              return False, f"OAuth2 отклонён: {rmsg[:120]}"
          return True, ""
      srv.login(user, pwd)
      return True, ""

  ctx = ssl.create_default_context()
  try:
      if use_ssl or port == 465:
          with smtplib.SMTP_SSL(host, port, context=ctx, timeout=25) as srv:
              ok, err = _auth(srv)
              if not ok:
                  return False, err
              srv.sendmail(user, [to_addr], msg.as_string())
      else:
          with smtplib.SMTP(host, port, timeout=25) as srv:
              srv.ehlo()
              if use_tls:
                  srv.starttls(context=ctx)
              ok, err = _auth(srv)
              if not ok:
                  return False, err
              srv.sendmail(user, [to_addr], msg.as_string())
      return True, ""
  except Exception as exc:
      return False, str(exc)


def build_test_message(sender, to_addr: str, subject: str, html_body: str, test_id: str):
  """Собирает помеченное тестовое письмо."""
  from_email = getattr(sender, "email", "")
  display = getattr(sender, "display_name", "") or ""
  msg = MIMEMultipart("alternative")
  msg["Subject"] = subject
  msg["From"] = f"{display} <{from_email}>" if display else from_email
  msg["To"] = to_addr
  msg["Date"] = formatdate(localtime=True)
  msg["Message-ID"] = make_msgid(domain=_domain_of(from_email) or "fmail.local")
  msg[TEST_HEADER] = test_id
  body = (html_body or "").strip() or "<p>FMailSender delivery test.</p>"
  text = re.sub(r"<[^>]+>", " ", body)
  text = re.sub(r"\s+", " ", text).strip()
  msg.attach(MIMEText(text or "FMailSender delivery test.", "plain", "utf-8"))
  msg.attach(MIMEText(body, "html", "utf-8"))
  return msg


def _imap_connect(account):
  """Открывает IMAP-соединение (XOAUTH2 для Microsoft, иначе LOGIN)."""
  host, port, use_ssl = _imap_host_for(account)
  if not host:
      raise RuntimeError("IMAP-хост не определён")
  if use_ssl:
      imap = imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context())
  else:
      imap = imaplib.IMAP4(host, port)

  if _is_ms(account.email):
      try:
          from core.oauth2_refresh import get_valid_access_token
          tok = get_valid_access_token(account)
      except Exception:
          tok = getattr(account, "access_token", "") or getattr(account, "oauth_token", "")
      if not tok:
          raise RuntimeError("Нет OAuth2-токена для Microsoft IMAP")
      auth = f"user={account.email}\x01auth=Bearer {tok}\x01\x01".encode()
      imap.authenticate("XOAUTH2", lambda _: auth)
  else:
      imap.login(account.email, getattr(account, "password", ""))
  return imap


def _list_junk_folders(imap) -> list[str]:
  """Возвращает имена spam-папок: по флагу \\Junk, иначе по известным именам."""
  junk: list[str] = []
  try:
      typ, data = imap.list()
  except Exception:
      typ, data = "NO", []
  if typ != "OK" or not data:
      return junk
  flagged: list[str] = []
  named: list[str] = []
  for raw in data:
      line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
      # Формат: (\HasNoChildren \Junk) "/" "Junk Email"
      m = re.match(r'\((?P<flags>[^)]*)\)\s+("[^"]*"|\S+)\s+("(?P<q>[^"]*)"|(?P<u>\S+))\s*$', line)
      if not m:
          continue
      flags = (m.group("flags") or "").lower()
      name = m.group("q") if m.group("q") is not None else (m.group("u") or "")
      if not name:
          continue
      if "\\junk" in flags or "\\spam" in flags:
          flagged.append(name)
      elif name.lower() in _JUNK_NAMES:
          named.append(name)
  # Уникализируем, сохраняя приоритет флага
  seen: set[str] = set()
  for n in flagged + named:
      if n not in seen:
          seen.add(n)
          junk.append(n)
  return junk


def _folder_has_test(imap, folder: str, test_id: str, subject_token: str) -> bool:
  """Ищет тестовое письмо в папке по заголовку, затем по теме."""
  try:
      typ, _ = imap.select(f'"{folder}"', readonly=True)
      if typ != "OK":
          return False
  except Exception:
      return False
  criteria = [
      ("HEADER", TEST_HEADER, f'"{test_id}"'),
      ("SUBJECT", f'"{subject_token}"'),
  ]
  for crit in criteria:
      try:
          typ, data = imap.search(None, *crit)
          if typ == "OK" and data and data[0] and data[0].split():
              return True
      except Exception:
          continue
  return False


def check_placement(seed, test_id: str, subject_token: str) -> str:
  """Определяет размещение тестового письма в seed-аккаунте.

  Возвращает: 'inbox' | 'spam' | 'not_found' | 'error:<msg>'.
  """
  imap = None
  try:
      imap = _imap_connect(seed)
      # Входящие имеют приоритет
      if _folder_has_test(imap, "INBOX", test_id, subject_token):
          return "inbox"
      for folder in _list_junk_folders(imap):
          if _folder_has_test(imap, folder, test_id, subject_token):
              return "spam"
      return "not_found"
  except Exception as exc:
      return f"error:{exc}"
  finally:
      if imap is not None:
          try:
              imap.logout()
          except Exception:
              pass


def run_delivery_test(
  sender,
  seeds: list,
  subject: str,
  html_body: str,
  timeout: int = 120,
  poll_interval: int = 6,
  progress: Optional[Callable[[str], None]] = None,
) -> dict:
  """Полный one-click тест размещения.

  1. Отправляет помеченное письмо с `sender` на каждый seed-адрес.
  2. Опрашивает IMAP каждого seed до обнаружения письма или таймаута.

  Возвращает dict: {test_id, results: {email: {sent, send_error, placement}}}.
  placement ∈ inbox | spam | not_found | pending | error:...
  """
  def _say(m: str) -> None:
      if progress:
          try:
              progress(m)
          except Exception:
              pass

  test_id = make_test_tag()
  subject_token = f"[FMT-{test_id}]"
  full_subject = f"{(subject or '').strip()} {subject_token}".strip()

  results: dict[str, dict] = {}
  pending = []
  for seed in seeds:
      addr = getattr(seed, "email", str(seed))
      _say(f"Отправка на {addr}…")
      msg = build_test_message(sender, addr, full_subject, html_body, test_id)
      ok, err = _smtp_send(sender, addr, msg)
      results[addr] = {"sent": ok, "send_error": err, "placement": "pending" if ok else "not_found"}
      if ok:
          pending.append(seed)

  if not pending:
      return {"test_id": test_id, "results": results}

  deadline = time.time() + timeout
  # Первая проверка чуть позже — письму нужно время дойти
  time.sleep(min(poll_interval, 5))
  while pending and time.time() < deadline:
      for seed in list(pending):
          addr = getattr(seed, "email", str(seed))
          _say(f"Проверка {addr}…")
          placement = check_placement(seed, test_id, subject_token)
          if placement in ("inbox", "spam"):
              results[addr]["placement"] = placement
              pending.remove(seed)
          elif placement.startswith("error:"):
              results[addr]["placement"] = placement
              pending.remove(seed)
      if pending and time.time() < deadline:
          time.sleep(poll_interval)

  for seed in pending:
      addr = getattr(seed, "email", str(seed))
      if results[addr]["placement"] == "pending":
          results[addr]["placement"] = "not_found"

  return {"test_id": test_id, "results": results}


# ════════════════════════════════════════════════════════════════════════
#  mail-tester.com — опциональная числовая оценка (legacy)
# ════════════════════════════════════════════════════════════════════════

def generate_test_address() -> tuple[str, str, str]:
  """
  Генерирует уникальный адрес mail-tester.com.
  Возвращает (test_email, result_url, uid).
  """
  uid = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
  email = f"test-{uid}@srv1.mail-tester.com"
  url = f"https://www.mail-tester.com/test-{uid}"
  return email, url, uid


def fetch_result(uid: str, timeout: int = 20) -> dict:
  """
  Получает результат с mail-tester.com (парсит HTML страницу).
  Вызывайте не ранее чем через 30 сек после отправки письма.
  """
  url = f"https://www.mail-tester.com/test-{uid}"
  result = {"score": None, "max_score": 10, "inbox_status": "Ожидание", "url": url, "received": False, "error": ""}

  try:
      req = urllib.request.Request(
          url,
          headers={
              "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
              "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
              "Accept-Language": "en-US,en;q=0.5",
          },
      )
      with urllib.request.urlopen(req, timeout=timeout) as resp:
          html = resp.read().decode("utf-8", errors="replace")

      if "havent received" in html.lower() or "we haven" in html.lower() or "not received" in html.lower():
          result["inbox_status"] = "Письмо ещё не получено"
          result["received"] = False
          return result

      score_m = re.search(r"(\d+(?:\.\d+)?)\s*/\s*10", html)
      if score_m:
          score = float(score_m.group(1))
          result["score"] = score
          result["received"] = True
          if score >= 9:
              result["inbox_status"] = f"Входящие ({score}/10) — отлично"
          elif score >= 7:
              result["inbox_status"] = f"Входящие ({score}/10) — хорошо"
          elif score >= 5:
              result["inbox_status"] = f"Возможно спам ({score}/10)"
          else:
              result["inbox_status"] = f"Спам ({score}/10)"
      else:
          result["inbox_status"] = "Результат обрабатывается"
          result["received"] = True

  except urllib.error.URLError as e:
      result["error"] = f"Сеть: {e.reason}"
  except Exception as e:
      result["error"] = str(e)

  return result


def open_result_browser(uid: str) -> None:
  """Открывает результат в системном браузере."""
  import webbrowser
  webbrowser.open(f"https://www.mail-tester.com/test-{uid}")

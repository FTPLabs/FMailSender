"""
Microsoft OAuth2 Token Auto-Refresh Module v1.0.0
Авто-обновление access_token через refresh_token для Outlook/Hotmail/Live.

Публичные client_id (не требуют client_secret):
  - d3590ed6-52b3-4102-aeff-aad2292ab01c  Microsoft Office
  - 08162f7c-0fd2-4200-a84a-f25a4db0b584  Thunderbird
  - 9e5f94bc-e8a4-4e73-b8be-63364c29d753  Outlook iOS

Формат файла аккаунтов:
  email|password|refresh_token
"""
from __future__ import annotations

import base64
import logging
import smtplib
import ssl
import threading
import time
from typing import Optional

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

logger = logging.getLogger("oauth2_refresh")

# ── Публичные client_id Microsoft ────────────────────────────────────────────
MS_CLIENT_IDS: list[str] = [
    "9e5f94bc-e8a4-4e73-b8be-63364c29d753",  # Outlook iOS — подтверждённо рабочий
    "08162f7c-0fd2-4200-a84a-f25a4db0b584",  # Thunderbird — запасной
    "d3590ed6-52b3-4102-aeff-aad2292ab01c",  # Microsoft Office — третий
]

# Два эндпоинта: consumers (v2) и live.com (v1) — пробуем оба
MS_TOKEN_URL   = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
MS_TOKEN_URL_V1 = "https://login.live.com/oauth20_token.srf"
MS_SMTP_SCOPE  = "https://outlook.office.com/SMTP.Send offline_access openid"

MICROSOFT_DOMAINS: frozenset[str] = frozenset({
    "outlook.com", "outlook.de", "outlook.fr", "outlook.es", "outlook.it",
    "outlook.co.uk", "outlook.jp", "outlook.ru", "outlook.nl", "outlook.be",
    "outlook.at", "outlook.com.br", "outlook.sa", "outlook.com.ar",
    "hotmail.com", "hotmail.co.uk", "hotmail.de", "hotmail.fr", "hotmail.es",
    "hotmail.it", "hotmail.ru",
    "live.com", "live.co.uk", "live.de", "live.fr", "live.ru",
    "msn.com", "windowslive.com",
})

_cache_lock = threading.Lock()
_token_cache: dict[str, "_TokenInfo"] = {}


class _TokenInfo:
    """Кэшированные OAuth2-токены для одного аккаунта."""
    __slots__ = ("access_token", "refresh_token", "expires_at", "client_id_used")

    def __init__(self, access_token: str, refresh_token: str, expires_in: int, client_id: str):
        self.access_token  = access_token
        self.refresh_token = refresh_token
        self.expires_at    = time.time() + expires_in
        self.client_id_used = client_id

    @property
    def is_valid(self) -> bool:
        return bool(self.access_token) and time.time() < (self.expires_at - 60)


def _try_refresh(client_id: str, refresh_token: str, timeout: float) -> Optional[dict]:
    """Одна попытка обновить токен через конкретный client_id. Пробует v2 и v1 эндпоинты."""
    if not _HAS_REQUESTS:
        return None
    for url, scope in [
        (MS_TOKEN_URL, MS_SMTP_SCOPE),
        (MS_TOKEN_URL_V1, "wl.imap wl.smtp"),
    ]:
        try:
            resp = _requests.post(
                url,
                data={
                    "grant_type":    "refresh_token",
                    "client_id":     client_id,
                    "refresh_token": refresh_token,
                    "scope":         scope,
                },
                timeout=timeout,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code == 200:
                return resp.json()
            logger.debug("refresh failed client=%s url=%s status=%s",
                         client_id[:8], url.split("/")[2], resp.status_code)
        except Exception as exc:
            logger.debug("refresh exc client=%s: %s", client_id[:8], exc)
    return None


def refresh_ms_token(email: str, refresh_token: str, timeout: float = 15.0) -> Optional[_TokenInfo]:
    """
    Обновляет Microsoft OAuth2 access_token через refresh_token.
    Перебирает все известные публичные client_id до первого успеха.

    Returns:
        _TokenInfo с новым access_token, или None если все попытки провалились.
    """
    if not refresh_token:
        return None
    for cid in MS_CLIENT_IDS:
        data = _try_refresh(cid, refresh_token, timeout)
        if data and data.get("access_token"):
            new_rt = data.get("refresh_token", refresh_token)
            info = _TokenInfo(
                access_token  = data["access_token"],
                refresh_token = new_rt,
                expires_in    = int(data.get("expires_in", 3600)),
                client_id     = cid,
            )
            with _cache_lock:
                _token_cache[email.lower()] = info
            logger.info("OAuth2 обновлён для %s (client=%s, ttl=%ds)",
                        email, cid[:8], data.get("expires_in", 3600))
            return info
    logger.warning("Не удалось обновить OAuth2 токен для %s", email)
    return None


def get_valid_access_token(account) -> str:
    """
    Возвращает актуальный access_token для аккаунта.
    Автоматически обновляет через refresh_token если истёк.

    Поддерживаемые поля SmtpAccount:
      - account.oauth_token       — текущий access_token (устаревшее имя)
      - account.access_token      — текущий access_token
      - account.token_expires_at  — unix timestamp истечения
      - account.refresh_token     — refresh_token для авто-обновления
    """
    email = account.email.lower()

    # 1. Проверяем глобальный кэш
    with _cache_lock:
        cached = _token_cache.get(email)
    if cached and cached.is_valid:
        return cached.access_token

    # 2. Проверяем поля аккаунта
    _at  = getattr(account, "access_token", "") or getattr(account, "oauth_token", "") or ""
    _exp = float(getattr(account, "token_expires_at", 0) or 0)
    _rt  = getattr(account, "refresh_token", "") or ""

    if _at and (_exp == 0 or time.time() < (_exp - 60)):
        # Токен ещё не истёк (или expires_at не задан)
        return _at

    # 3. Обновляем через refresh_token
    if not _rt:
        return _at  # нет RT — возвращаем что есть

    logger.info("Обновляем OAuth2 для %s...", email)
    info = refresh_ms_token(email, _rt)
    if info:
        # Используем lock аккаунта если он есть (SmtpAccount имеет _lock),
        # чтобы избежать race condition при параллельных потоках.
        _acct_lock = getattr(account, "_lock", None)
        if _acct_lock is not None:
            with _acct_lock:
                account.access_token     = info.access_token
                account.token_expires_at = info.expires_at
                if info.refresh_token and info.refresh_token != _rt:
                    account.refresh_token = info.refresh_token
                account.oauth_token = info.access_token
        else:
            account.access_token     = info.access_token
            account.token_expires_at = info.expires_at
            if info.refresh_token and info.refresh_token != _rt:
                account.refresh_token = info.refresh_token
            account.oauth_token = info.access_token
        return info.access_token

    return _at  # fallback — старый токен


def build_xoauth2(email: str, access_token: str) -> str:
    """Формирует SASL XOAUTH2-строку для SMTP AUTH."""
    raw = f"user={email}\x01auth=Bearer {access_token}\x01\x01"
    return base64.b64encode(raw.encode()).decode()


def is_ms_domain(email: str) -> bool:
    """Проверяет, является ли домен Microsoft."""
    return email.split("@")[-1].lower() in MICROSOFT_DOMAINS


def test_oauth2_smtp(
    email: str,
    refresh_token: str,
    host: str = "smtp.office365.com",
    port: int = 587,
    timeout: float = 15.0,
) -> tuple[bool, str]:
    """
    Тестирует SMTP-соединение через OAuth2/XOAUTH2.

    Алгоритм:
      1. Получает actess_token через refresh_ms_token
      2. Подключается к SMTP (STARTTLS на 587, SSL на 465)
      3. AUTH XOAUTH2 — проверяет результат

    Returns:
        (True, "OK сообщение") или (False, "Текст ошибки")
    """
    # Шаг 1: access_token
    info = refresh_ms_token(email, refresh_token, timeout=timeout)
    if not info:
        return False, (
            "OAuth2 refresh провалился — refresh_token отклонён Microsoft.\n"
            "Причины: токен просрочен, аккаунт заблокирован, или SMTP AUTH отключён.\n"
            "Решение: зайдите в Outlook, разрешите SMTP в настройках приложения."
        )

    xoauth2 = build_xoauth2(email, info.access_token)

    # Шаг 2: SMTP
    try:
        ctx = ssl.create_default_context()
        if port == 465:
            smtp = smtplib.SMTP_SSL(host, port, context=ctx, timeout=timeout)
        else:
            smtp = smtplib.SMTP(host, port, timeout=timeout)
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.ehlo()

        # Шаг 3: AUTH XOAUTH2
        code, resp_bytes = smtp.docmd("AUTH", "XOAUTH2 " + xoauth2)
        raw = resp_bytes.decode("utf-8", errors="replace") if isinstance(resp_bytes, bytes) else str(resp_bytes)

        try:
            smtp.quit()
        except Exception:
            pass

        if code == 235:
            return True, f"OAuth2 AUTH успешно — {email}"

        # Детальная расшифровка ошибок Microsoft
        if code == 535:
            return False, f"535 Invalid credentials — access_token отклонён. Токен возможно просрочен."
        if code == 534:
            return False, f"534 AUTH Required — SMTP AUTH не включён для аккаунта {email}. Включите в настройках Outlook."
        if "TLS" in raw.upper() or "STARTTLS" in raw.upper():
            return False, f"TLS ошибка: {raw[:200]}"
        return False, f"SMTP код {code}: {raw[:200]}"

    except smtplib.SMTPConnectError as exc:
        return False, f"Не удалось подключиться к {host}:{port} — {exc}"
    except smtplib.SMTPServerDisconnected:
        return False, f"Сервер разорвал соединение (возможно IP заблокирован)"
    except ssl.SSLError as exc:
        return False, f"SSL/TLS ошибка: {exc}"
    except OSError as exc:
        return False, f"Сетевая ошибка: {exc}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def parse_pipe_account_line(line: str) -> Optional[dict]:
    """
    Разбирает строку в pipe-формате: email|password|refresh_token
    Используется для импорта аккаунтов Outlook с OAuth2.

    Returns dict с ключами: email, password, refresh_token
    или None если строка невалидна.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = line.split("|")
    if len(parts) < 2:
        return None
    email = parts[0].strip()
    if not email or "@" not in email:
        return None
    password = parts[1].strip()
    refresh_token = parts[2].strip() if len(parts) >= 3 else ""
    return {
        "email": email,
        "password": password,
        "refresh_token": refresh_token,
    }

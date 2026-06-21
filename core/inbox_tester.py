"""
FMailSender Inbox Tester v1.0.0
Проверяет доставляемость письма — inbox vs spam.
Использует mail-tester.com (бесплатно, без регистрации).
"""
from __future__ import annotations

import random
import re
import string
import urllib.error
import urllib.request
from typing import Optional


def generate_test_address() -> tuple[str, str, str]:
    """
    Генерирует уникальный адрес mail-tester.com.
    Возвращает (test_email, result_url, uid).
    Бесплатно: просто отправьте письмо на test_email,
    затем откройте result_url в браузере.
    """
    uid = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f"test-{uid}@srv1.mail-tester.com"
    url = f"https://www.mail-tester.com/test-{uid}"
    return email, url, uid


def fetch_result(uid: str, timeout: int = 20) -> dict:
    """
    Получает результат с mail-tester.com (парсит HTML страницу).
    Вызывайте не ранее чем через 30 сек после отправки письма.

    Возвращает dict:
      score      - float 0-10 (None если письмо ещё не получено)
      max_score  - 10
      inbox_status - строка с вердиктом
      url        - ссылка на результат
      received   - bool (было ли получено письмо)
      error      - строка с ошибкой или ""
    """
    url = f"https://www.mail-tester.com/test-{uid}"
    result = {"score": None, "max_score": 10, "inbox_status": "⏳ Ожидание", "url": url, "received": False, "error": ""}

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

        # Письмо ещё не получено?
        if "havent received" in html.lower() or "we haven" in html.lower() or "not received" in html.lower():
            result["inbox_status"] = "⏳ Письмо ещё не получено"
            result["received"] = False
            return result

        # Парсим оценку (X/10 или X.X/10)
        score_m = re.search(r"(\d+(?:\.\d+)?)\s*/\s*10", html)
        if score_m:
            score = float(score_m.group(1))
            result["score"] = score
            result["received"] = True
            if score >= 9:
                result["inbox_status"] = f"✅ Входящие ({score}/10) — отлично"
            elif score >= 7:
                result["inbox_status"] = f"✅ Входящие ({score}/10) — хорошо"
            elif score >= 5:
                result["inbox_status"] = f"⚠️ Возможно спам ({score}/10)"
            else:
                result["inbox_status"] = f"🚫 Спам ({score}/10)"
        else:
            result["inbox_status"] = "⏳ Результат обрабатывается"
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
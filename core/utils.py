"""
Общие утилиты FMailSender — единственный источник истины для validate_email_format.
Импортируйте validate_email_format ТОЛЬКО отсюда, чтобы избежать циклических импортов.
"""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$",
    re.ASCII,
)


def validate_email_format(email: str) -> bool:
    """Базовая проверка формата email-адреса (RFC 5321 subset).

    Возвращает True если строка выглядит как валидный email.
    Не делает DNS-запросов — только синтаксическая проверка.
    """
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if len(email) > 320:
        return False
    local, _, domain = email.rpartition("@")
    if not local or not domain:
        return False
    if len(local) > 64 or len(domain) > 253:
        return False
    return bool(_EMAIL_RE.match(email))

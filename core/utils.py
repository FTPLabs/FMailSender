"""
Общие утилиты FMailSender.
- validate_email_format: единственный источник истины для валидации email
- strip_html: единственный источник истины для очистки HTML
Импортируйте только отсюда, чтобы избежать циклических импортов.
"""
from __future__ import annotations

import html as _html_stdlib
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


def strip_html(html_str: str, max_len: int | None = None) -> str:
    """Удаляет HTML-теги и декодирует entities (&amp;, &nbsp; и т.д.).

    Единственный источник истины для HTML→plain-text конвертации.
    Используется в sender.py, spam_checker.py и ai_fixer.py.

    Args:
        html_str: Строка с HTML-разметкой.
        max_len: Если задан — усекает результат до max_len символов.

    Returns:
        Чистый текст без тегов и с декодированными entities.
    """
    if not html_str:
        return ""
    text = re.sub(r"<[^>]+>", "", html_str)
    text = _html_stdlib.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if max_len is not None:
        text = text[:max_len]
    return text


def resource_path(*parts: str) -> str:
    """Абсолютный путь к ресурсу. Работает и в dev, и в PyInstaller-бандле.

    В собранном .exe ресурсы лежат в sys._MEIPASS; в dev — относительно корня
    проекта (core/ -> ..). Используйте для assets/images, assets/sounds и т.п.
    """
    import sys
    from pathlib import Path
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = Path(__file__).resolve().parent.parent  # core/ -> корень проекта
    return str(Path(base).joinpath(*parts))

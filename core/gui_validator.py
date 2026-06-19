"""
FMailSender GUI Validator — utility functions for validating UI form inputs.
Usage:
    from core.gui_validator import validate_email, validate_smtp_host, validate_port
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class FieldError:
    field: str
    message: str

    def __str__(self) -> str:
        return f"{self.field}: {self.message}"


_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", re.IGNORECASE
)
_HOST_RE = re.compile(
    r"^(([a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}|(\d{1,3}\.){3}\d{1,3}|\[?[0-9a-fA-F:]+\]?)$"
)


def validate_email(value: str) -> Tuple[bool, str]:
    v = value.strip()
    if not v:
        return False, "Email не может быть пустым"
    if "@" not in v:
        return False, "Email должен содержать @"
    if not _EMAIL_RE.match(v):
        return False, "Неверный формат email"
    local, domain = v.rsplit("@", 1)
    if len(local) > 64:
        return False, "Локальная часть email слишком длинная (max 64)"
    if len(domain) > 255:
        return False, "Домен email слишком длинный (max 255)"
    return True, ""


def validate_smtp_host(value: str) -> Tuple[bool, str]:
    v = value.strip()
    if not v:
        return False, "SMTP-хост не может быть пустым"
    if not _HOST_RE.match(v):
        return False, f"Недопустимый SMTP-хост: '{v}'"
    return True, ""


def validate_port(value) -> Tuple[bool, str]:
    try:
        port = int(value)
    except (ValueError, TypeError):
        return False, "Порт должен быть числом"
    if port < 1 or port > 65535:
        return False, f"Порт должен быть в диапазоне 1-65535 (получено {port})"
    return True, ""


def validate_password(value: str, min_len: int = 4) -> Tuple[bool, str]:
    if not value:
        return False, "Пароль не может быть пустым"
    if len(value) < min_len:
        return False, f"Пароль слишком короткий (минимум {min_len} символов)"
    return True, ""


def validate_account_form(email: str, password: str, host: str, port) -> List[FieldError]:
    errors: List[FieldError] = []
    for fn, field, val in [
        (validate_email, "Email", email),
        (validate_password, "Пароль", password),
        (validate_smtp_host, "SMTP-хост", host),
        (validate_port, "Порт", port),
    ]:
        ok, reason = fn(val)
        if not ok:
            errors.append(FieldError(field, reason))
    return errors

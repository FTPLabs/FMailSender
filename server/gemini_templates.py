"""Server-only Gemini HTML template service.

Gemini credentials remain in the license-server environment. This module receives
only a short editorial brief or a user-owned template and returns safe, readable
email HTML; it never attempts to bypass filtering or mutate delivery headers.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

import aiohttp
from fastapi import HTTPException

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
_MAX_HTML = 20_000
_MAX_TEXT = 8_000
_MAX_BRIEF = 1_200
_RATE_LIMIT = 6
_RATE_WINDOW = 600.0
_REQUESTS: dict[str, deque[float]] = defaultdict(deque)
_DANGEROUS_BLOCKS = re.compile(r"(?is)<(script|iframe|object|embed|form)\b.*?</\1\s*>")
_EVENT_ATTRS = re.compile(r"(?is)\\s+on[a-z]+\\s*=\\s*(?:\\\"[^\\\"]*\\\"|'[^']*'|[^\\s>]+)")
_SCRIPT_URLS = re.compile(r"(?is)(href|src)\\s*=\\s*([\\\"'])\\s*(?:javascript:|data:text/html)[^\\\"']*\\2")


def _take_rate_slot(license_key: str) -> None:
    now = time.monotonic()
    digest = hashlib.sha256(license_key.encode("utf-8")).hexdigest()
    bucket = _REQUESTS[digest]
    while bucket and now - bucket[0] >= _RATE_WINDOW:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Лимит AI-операций: повторите позже.")
    bucket.append(now)


def _clean_html(value: str) -> str:
    clean = _DANGEROUS_BLOCKS.sub("", value)
    clean = _EVENT_ATTRS.sub("", clean)
    clean = _SCRIPT_URLS.sub(r'\1="#"', clean)
    return clean.strip()


def _extract_text(payload: dict[str, Any]) -> str:
    for step in payload.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for block in step.get("content", []):
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                return block["text"]
    raise HTTPException(status_code=502, detail="Gemini не вернул текстовый результат.")


def _parse_result(text: str) -> dict[str, str]:
    source = text.strip()
    if source.startswith("```"):
        source = re.sub(r"^```(?:json)?\s*|\s*```$", "", source, flags=re.IGNORECASE)
    try:
        data = json.loads(source)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Gemini вернул некорректный формат шаблона.") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Gemini вернул некорректную структуру шаблона.")
    subject = str(data.get("subject", "")).strip()
    body_html = _clean_html(str(data.get("body_html", "")))
    body_text = str(data.get("body_text", "")).strip()
    if not subject or not body_html or not body_text:
        raise HTTPException(status_code=502, detail="Gemini не заполнил обязательные части шаблона.")
    if len(subject) > 180 or len(body_html) > _MAX_HTML or len(body_text) > _MAX_TEXT:
        raise HTTPException(status_code=502, detail="Gemini вернул шаблон превышающего допустимый размер.")
    return {"subject": subject, "body_html": body_html, "body_text": body_text, "model": _MODEL}


async def create_template(*, license_key: str, mode: str, brief: str, subject: str, body_html: str, body_text: str) -> dict[str, str]:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=503, detail="AI-функция временно не настроена.")
    if mode not in {"generate", "refine"}:
        raise HTTPException(status_code=400, detail="Неизвестный режим AI-операции.")
    brief = brief.strip()
    subject = subject.strip()
    body_html = body_html.strip()
    body_text = body_text.strip()
    if len(brief) > _MAX_BRIEF or len(subject) > 180 or len(body_html) > _MAX_HTML or len(body_text) > _MAX_TEXT:
        raise HTTPException(status_code=413, detail="Превышен допустимый размер запроса AI.")
    if mode == "generate" and not brief:
        raise HTTPException(status_code=400, detail="Опишите цель и аудиторию шаблона.")
    if mode == "refine" and not (subject or body_html or body_text):
        raise HTTPException(status_code=400, detail="Добавьте содержимое шаблона для улучшения.")

    _take_rate_slot(license_key)
    instruction = (
        "You are an email template editor for legitimate, consent-based communication. "
        "Return only a JSON object with subject, body_html, and body_text. "
        "Produce readable, accessible HTML with inline-safe styles, a visible unsubscribe placeholder {{unsubscribe_url}}, "
        "and a plain-text alternative. Preserve valid {{name}}, {{email}}, {{company}} placeholders. "
        "Do not use hidden text, tracking pixels, obfuscated text, spintax, misleading claims, scripts, forms, iframes, "
        "or instructions intended to evade spam filters. Do not invent personal facts. "
    )
    if mode == "generate":
        task = f"Create a new template from this brief: {brief}"
    else:
        task = "Improve clarity, accessibility and honest call-to-action of this user-owned template without changing its intent."
    prompt = "\n\n".join([instruction, task, f"Brief: {brief}", f"Subject: {subject}", f"HTML: {body_html}", f"Text: {body_text}"])
    schema = {
        "type": "object",
        "properties": {
            "subject": {"type": "string"},
            "body_html": {"type": "string"},
            "body_text": {"type": "string"},
        },
        "required": ["subject", "body_html", "body_text"],
    }
    payload = {
        "model": _MODEL,
        "store": False,
        "input": prompt,
        "response_format": {"type": "text", "mime_type": "application/json", "schema": schema},
    }
    timeout = aiohttp.ClientTimeout(total=45)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(_GEMINI_URL, headers={"x-goog-api-key": key, "Content-Type": "application/json"}, json=payload) as response:
                raw = await response.json(content_type=None)
                if response.status != 200:
                    raise HTTPException(status_code=502, detail="Gemini временно недоступен. Повторите попытку позже.")
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Gemini не ответил за отведённое время.") from exc
    except aiohttp.ClientError as exc:
        raise HTTPException(status_code=502, detail="Не удалось установить соединение с Gemini.") from exc
    return _parse_result(_extract_text(raw))

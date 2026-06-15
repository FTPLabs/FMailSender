"""
AI-powered email spam fixer.
Calls OpenAI API (or compatible) to analyze spam issues and suggest fixes.
API key: env OPENAI_API_KEY  (or prompt user in settings).
"""
from __future__ import annotations
import json
import os
import re as _re_module
from typing import Optional


def _get_openai_key() -> str | None:
    return os.environ.get("OPENAI_API_KEY", "").strip() or None


def _re_strip_html(html: str, max_len: int = 3000) -> str:
    """Strip HTML tags and truncate to max_len characters."""
    text = _re_module.sub(r"<[^>]+>", "", html)
    text = _re_module.sub(r"\s+", " ", text).strip()
    return text[:max_len]


class AiFixResult:
    def __init__(self, subject: str, body_html: str, explanation: str):
        self.subject = subject
        self.body_html = body_html
        self.explanation = explanation


class AiSpamFixer:
    """Uses OpenAI-compatible API to rewrite email content to pass spam filters."""

    BASE_URL = "https://api.openai.com/v1"
    MODEL = "gpt-4o-mini"

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._api_key = api_key or _get_openai_key()
        self._base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or self.BASE_URL).rstrip("/")

    @property
    def has_key(self) -> bool:
        return bool(self._api_key)

    def fix_email(
        self,
        subject: str,
        body_html: str,
        issues: list[str],
        warnings: list[str],
    ) -> AiFixResult:
        """
        Rewrites the email subject and body to avoid spam triggers.
        Returns AiFixResult with improved subject, body_html, and explanation.
        Raises RuntimeError if API key is not set or request fails.
        """
        if not self._api_key:
            raise RuntimeError(
                "OPENAI_API_KEY не установлен.\n"
                "Задайте переменную окружения OPENAI_API_KEY и перезапустите приложение."
            )

        issues_text = "\n".join(f"- {i}" for i in issues) if issues else "нет"
        warnings_text = "\n".join(f"- {w}" for w in warnings) if warnings else "нет"

        system_prompt = (
            "Ты эксперт по email-маркетингу и доставляемости писем. "
            "Твоя задача — переписать тему и тело письма так, чтобы письмо "
            "гарантированно попало во входящие, а не в спам. "
            "Сохраняй смысл и язык оригинала (русский или английский). "
            "Верни ответ строго в JSON формате."
        )

        user_prompt = f"""Анализ спам-фильтра показал следующие проблемы:

ПРОБЛЕМЫ:
{issues_text}

ПРЕДУПРЕЖДЕНИЯ:
{warnings_text}

ТЕКУЩАЯ ТЕМА:
{subject}

ТЕКУЩЕЕ ТЕЛО (HTML):
{_re_strip_html(body_html, 3000)}

Перепиши письмо, устранив все проблемы. Верни JSON:
{{
  "subject": "улучшенная тема",
  "body_html": "улучшенное тело в HTML",
  "explanation": "кратко что изменено и почему"
}}"""

        payload = json.dumps({
            "model": self.MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 3000,
            "temperature": 0.3,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API ошибка {e.code}: {body[:300]}")

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(
                f"OpenAI API вернул неожиданный ответ: {str(data)[:300]}"
            ) from exc

        import re as _re_j
        _jm = _re_j.search(r'```(?:json)?\s*([\s\S]+?)```', content)
        if _jm:
            content = _jm.group(1).strip()
        else:
            _om = _re_j.search(r'\{[\s\S]+\}', content)
            if _om:
                content = _om.group(0).strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OpenAI вернул невалидный JSON: {content[:300]}") from exc
        return AiFixResult(
            subject=parsed.get("subject", subject),
            body_html=parsed.get("body_html", body_html),
            explanation=parsed.get("explanation", ""),
        )

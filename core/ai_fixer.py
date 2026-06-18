"""
AI-powered email spam fixer.
Calls OpenAI API (or compatible) to analyze spam issues and suggest fixes.
API key: env OPENAI_API_KEY  (or prompt user in settings).
"""
from __future__ import annotations
import json
import os
import re as _re_module
import threading
import urllib.error
import urllib.request
from typing import Callable, Optional


def _get_openai_key() -> str | None:
    return os.environ.get("OPENAI_API_KEY", "").strip() or None


def _re_strip_html(html: str, max_len: int = 3000) -> str:
    """Strip HTML tags and truncate to max_len characters."""
    from core.utils import strip_html as _su
    return _su(html, max_len=max_len)


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
        """Rewrites email to avoid spam triggers. Синхронный — блокирует поток.
        Для GUI используйте fix_email_in_thread().
        Raises RuntimeError если API key не задан или запрос упал.
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

        user_prompt = (
            "Анализ спам-фильтра показал следующие проблемы:\n\n"
            f"ПРОБЛЕМЫ:\n{issues_text}\n\n"
            f"ПРЕДУПРЕЖДЕНИЯ:\n{warnings_text}\n\n"
            f"ТЕКУЩАЯ ТЕМА:\n{subject}\n\n"
            "ТЕКУЩЕЕ ТЕЛО (HTML):\n" + _re_strip_html(body_html, 3000) + "\n\n"
            "Перепиши письмо, устранив все проблемы. Верни JSON:\n"
            '{\n  "subject": "улучшенная тема",\n'
            '  "body_html": "улучшенное тело в HTML",\n'
            '  "explanation": "кратко что изменено и почему"\n}'
        )

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
        except urllib.error.URLError as e:
            raise RuntimeError(f"Сетевая ошибка при обращении к OpenAI API: {e.reason}")
        except TimeoutError:
            raise RuntimeError("Таймаут OpenAI API (>60с). Проверьте интернет-соединение.")

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(
                f"OpenAI API вернул неожиданный ответ: {str(data)[:300]}"
            ) from exc

        # Извлекаем JSON из ответа (может быть обёрнут в markdown-блок)
        _jm = _re_module.search(r'```(?:json)?\s*([\s\S]+?)```', content)
        if _jm:
            content = _jm.group(1).strip()
        else:
            _om = _re_module.search(r'\{[\s\S]+\}', content)
            if _om:
                content = _om.group(0).strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OpenAI вернул невалидный JSON: {content[:300]}") from exc

        return AiFixResult(
            subject=parsed.get("subject", subject),
            body_html=parsed.get("body_html", body_html),
            explanation=parsed.get("explanation", ""),
        )

    def fix_email_in_thread(
        self,
        subject: str,
        body_html: str,
        issues: "list[str]",
        warnings_list: "list[str]",
        on_result: "Callable[[Optional[AiFixResult], Optional[Exception]], None]",
    ) -> threading.Thread:
        """FIX БАГ-4: Запускает fix_email() в daemon-потоке — GUI не блокируется.

        on_result(result, None) — при успехе.
        on_result(None, exc)   — при ошибке.

        Пример (PyQt6):
            def _on_done(res, err):
                if err:
                    QMessageBox.critical(self, "AI ошибка", str(err))
                else:
                    self._apply_ai_result(res)
            fixer.fix_email_in_thread(subj, html, issues, warns, _on_done)
        """
        def _run() -> None:
            try:
                result = self.fix_email(subject, body_html, issues, warnings_list)
                on_result(result, None)
            except Exception as exc:  # noqa: BLE001
                on_result(None, exc)

        t = threading.Thread(target=_run, daemon=True, name="AiSpamFixer")
        t.start()
        return t

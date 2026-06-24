"""
FMailSender Email Uniqueizer v2.0.0 — HTML-safe, deliverability-positive.

Принцип: уникализировать письмо так, чтобы оно ПОПАДАЛО ВО «ВХОДЯЩИЕ», а не в спам.

Почему переписано (v1 -> v2):
  Старые техники (гомоглифы латиница/кириллица, zero-width символы, скрытый
  бело-на-белом текст, unicode variation selectors, случайные HTML-сущности,
  невидимые <span>) — это КЛАССИЧЕСКИЕ СПАМ-СИГНАЛЫ. Спам-фильтры (SpamAssassin,
  Gmail, Outlook) детектируют их и понижают репутацию письма. Плюс наивная
  regex-замена `(?<=>)[^<]+(?=<)` ЛОМАЛА HTML: цепляла текст внутри <script>/
  <style>, путала атрибуты, а добавление data-* в конец тега ломало self-closing
  теги (<img .../>).

v2 делает две вещи правильно:
  1. БЕЗОПАСНОСТЬ HTML: все текстовые правки идут ТОЛЬКО по текстовым узлам через
     токенайзер (теги/комментарии/script/style/doctype не трогаются вообще).
     Структура тегов остаётся инвариантной (см. verify_structure).
  2. ДОСТАВЛЯЕМОСТЬ: оставлены только безопасные приёмы вариативности —
     spintax {вариант1|вариант2} (реальная замена текста), доброкачественные
     fingerprint-атрибуты/комментарии, микро-вариации CSS, перестановка
     font-family, &nbsp; после пунктуации. Опционально — tracking pixel (выкл).
     Для глубокой переформулировки — AI (ai_rephrase / OpenAI / free-провайдеры).
"""
from __future__ import annotations

import hashlib
import random
import re
import string
import urllib.error
import urllib.request
import uuid
from typing import Dict, List, Optional, Tuple


# ============================================================
# Утилиты
# ============================================================
def _rid(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def _hash12() -> str:
    return hashlib.md5(uuid.uuid4().bytes).hexdigest()[:12]


# Регэксп, выделяющий ВСЁ, что НЕ является видимым текстовым узлом:
# комментарии, CDATA, doctype, целые блоки <script>/<style>, любые теги.
_NON_TEXT_RE = re.compile(
    r"(?:<!--.*?-->"
    r"|<!\[CDATA\[.*?\]\]>"
    r"|<![^>]*>"
    r"|<script\b[^>]*>.*?</script>"
    r"|<style\b[^>]*>.*?</style>"
    r"|<[^>]+>)",
    re.IGNORECASE | re.DOTALL,
)


def _walk_text_nodes(html: str, transform) -> str:
    """Применяет transform(text)->text ТОЛЬКО к видимым текстовым узлам.

    Теги, атрибуты, комментарии, содержимое <script>/<style>, doctype остаются
    нетронутыми. Это гарантирует, что структура HTML не ломается.
    """
    out: List[str] = []
    pos = 0
    for m in _NON_TEXT_RE.finditer(html):
        if m.start() > pos:
            chunk = html[pos:m.start()]
            if chunk:
                try:
                    out.append(transform(chunk))
                except Exception:
                    out.append(chunk)
        out.append(m.group(0))
        pos = m.end()
    if pos < len(html):
        chunk = html[pos:]
        try:
            out.append(transform(chunk))
        except Exception:
            out.append(chunk)
    return "".join(out)


def _tag_sequence(html: str) -> List[str]:
    """Возвращает последовательность имён тегов (для проверки инвариантности)."""
    return [t.lower() for t in re.findall(r"<\s*(/?[a-zA-Z][\w:-]*)", html)]


def verify_structure(before: str, after: str) -> bool:
    """True, если последовательность тегов не изменилась (текст-онли техники)."""
    return _tag_sequence(before) == _tag_sequence(after)


# ============================================================
# SPINTAX — главная безопасная техника: {вариант1|вариант2|вариант3}
# ============================================================
_SPINTAX_RE = re.compile(r"\{([^{}]*\|[^{}]*)\}")


def _spin_once(text: str) -> str:
    def _pick(m: re.Match) -> str:
        opts = m.group(1).split("|")
        return random.choice(opts)
    # несколько проходов — на случай вложенности после первой подстановки
    for _ in range(5):
        new = _SPINTAX_RE.sub(_pick, text)
        if new == text:
            break
        text = new
    return text


def technique_spintax(html: str) -> str:
    """Раскрывает spintax {a|b|c} -> один из вариантов. Только в текстовых узлах.

    Это самый «честный» приём: текст реально различается у каждого получателя,
    что улучшает доставляемость и не триггерит спам-фильтры.
    """
    if "{" not in html or "|" not in html:
        return html
    return _walk_text_nodes(html, _spin_once)


def spin_text(text: str) -> str:
    """Раскрывает spintax в обычной строке (для темы письма)."""
    return _spin_once(text)


# ============================================================
# &nbsp; после пунктуации (тонко, безопасно, невидимо)
# ============================================================
def technique_nbsp(html: str, ratio: float = 0.15) -> str:
    def _inject(text: str) -> str:
        out = []
        n = len(text)
        for i, ch in enumerate(text):
            out.append(ch)
            if ch in ".!?,:;" and i < n - 1 and text[i + 1] == " " and random.random() < ratio:
                out.append("&nbsp;")
        return "".join(out)
    return _walk_text_nodes(html, _inject)


# ============================================================
# data-* атрибуты на блочных тегах (fingerprint) — self-closing safe
# ============================================================
def technique_data_attrs(html: str, ratio: float = 0.5) -> str:
    """Добавляет data-mid/data-ts к части блочных тегов.

    Корректно работает с self-closing тегами (<img .../>): атрибуты
    вставляются ПЕРЕД закрывающим '/>' или '>'.
    """
    def _add(m: re.Match) -> str:
        if random.random() > ratio:
            return m.group(0)
        tag = m.group(0)
        attrs = f' data-mid="{_rid(8)}" data-ts="{random.randint(1_000_000, 9_999_999)}"'
        if tag.endswith("/>"):
            return tag[:-2] + attrs + "/>"
        return tag[:-1] + attrs + ">"
    return re.sub(r"<(?:td|tr|div|p|table|tbody|section|article)\b[^>]*?/?>",
                  _add, html, flags=re.IGNORECASE)


# ============================================================
# Доброкачественные HTML-комментарии (после закрывающих блочных тегов)
# ============================================================
def technique_random_comments(html: str, count: int = 4) -> str:
    tags = list(re.finditer(r"</(?:td|p|div|tr|table|section)>", html, re.IGNORECASE))
    if not tags:
        return html
    for _ in range(count):
        t = random.choice(tags)
        comment = f"<!-- {_hash12()} -->"
        html = html[:t.end()] + comment + html[t.end():]
        tags = list(re.finditer(r"</(?:td|p|div|tr|table|section)>", html, re.IGNORECASE))
    return html


# ============================================================
# CSS микро-вариации (±1 к hex-цвету) — только внутри CSS
# ============================================================
def technique_css_micro(html: str) -> str:
    uid = _rid(16)
    marker = (
        f'<meta name="x-uid" content="{uid}">'
        f'<meta name="x-ts" content="{random.randint(100_000, 999_999)}">'
    )

    def _vary(m: re.Match) -> str:
        c = m.group(1)
        try:
            r2 = max(0, min(255, int(c[0:2], 16) + random.randint(-1, 1)))
            g2 = max(0, min(255, int(c[2:4], 16) + random.randint(-1, 1)))
            b2 = max(0, min(255, int(c[4:6], 16) + random.randint(-1, 1)))
            return f"#{r2:02x}{g2:02x}{b2:02x}"
        except Exception:
            return m.group(0)

    def _vary_css(css_text: str) -> str:
        return re.sub(r"#([0-9a-fA-F]{6})\b", _vary, css_text)

    html = re.sub(r"(<style[^>]*>)(.*?)(</style>)",
                  lambda m: m.group(1) + _vary_css(m.group(2)) + m.group(3),
                  html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'(style\s*=\s*")([^"]+)(")',
                  lambda m: m.group(1) + _vary_css(m.group(2)) + m.group(3),
                  html, flags=re.IGNORECASE)
    html = re.sub(r"(style\s*=\s*')([^']+)(')",
                  lambda m: m.group(1) + _vary_css(m.group(2)) + m.group(3),
                  html, flags=re.IGNORECASE)
    if re.search(r"<head[^>]*>", html, re.IGNORECASE):
        html = re.sub(r"(<head[^>]*>)", r"\1" + marker, html, count=1, flags=re.IGNORECASE)
    return html


# ============================================================
# CSS custom properties (уникальный отпечаток в :root)
# ============================================================
def technique_css_custom_props(html: str) -> str:
    uid = _rid(16)
    ts = random.randint(1_000_000, 9_999_999)
    style = f'<style>:root{{--x-uid:"{uid}";--x-ts:"{ts}"}}</style>'
    if "</head>" in html.lower():
        return re.sub(r"(</head>)", style + r"\1", html, count=1, flags=re.IGNORECASE)
    return style + html


# ============================================================
# Перестановка font-family (сохраняем generic в конце)
# ============================================================
def technique_font_stack(html: str) -> str:
    def _shuffle(m: re.Match) -> str:
        raw = m.group(1).strip().rstrip(";")
        fonts: list[str] = []
        buf = ""
        in_quote: str | None = None
        for ch in raw:
            if ch in ('"', "'") and not in_quote:
                in_quote = ch
                buf += ch
            elif in_quote and ch == in_quote:
                in_quote = None
                buf += ch
            elif ch == "," and not in_quote:
                if buf.strip():
                    fonts.append(buf.strip())
                buf = ""
            else:
                buf += ch
        if buf.strip():
            fonts.append(buf.strip())
        if len(fonts) <= 2:
            return m.group(0)
        generic = fonts[-1]
        specific = fonts[:-1]
        random.shuffle(specific)
        result = []
        for f in specific + [generic]:
            f_inner = f.strip().strip("'\"")
            if " " in f_inner and not f.strip().startswith(("'", '"')):
                result.append(f"'{f_inner}'")
            else:
                result.append(f)
        return "font-family: " + ", ".join(result)
    return re.sub(r"font-family:\s*([^;{}]+)", _shuffle, html)


# ============================================================
# UUID fingerprint — уникальный токен на каждое письмо
# ============================================================
def technique_uuid_fingerprint(html: str) -> str:
    """Embed a unique per-email UUID as a hidden meta tag and inline style variable.

    Adds two invisible markers:
      1. <meta name="x-mid" content="<uuid>"> in <head> (or top of body)
      2. A CSS custom property --x-uid on the root element
    Both are invisible to readers but make every email cryptographically distinct.
    No spam signals: meta tags and CSS vars are standard and ignored by filters.
    """
    uid = str(uuid.uuid4())
    short = uid.replace("-", "")[:16]
    meta_tag = f'<meta name="x-mid" content="{uid}">'
    css_var = f'<style>:root{{--x-uid:"{short}";}}</style>'

    # Inject into <head> if present, otherwise prepend to body
    if re.search(r"<head\b[^>]*>", html, re.IGNORECASE):
        html = re.sub(
            r"(<head\b[^>]*>)",
            r"\1" + meta_tag + css_var,
            html, count=1, flags=re.IGNORECASE
        )
    elif re.search(r"<body\b[^>]*>", html, re.IGNORECASE):
        html = re.sub(
            r"(<body\b[^>]*>)",
            r"\1" + meta_tag + css_var,
            html, count=1, flags=re.IGNORECASE
        )
    else:
        html = meta_tag + css_var + html
    return html


# ============================================================
# Tracking pixel (опционально, выключен по умолчанию)
# ============================================================
def technique_tracking_pixel(html: str) -> str:
    uid = str(uuid.uuid4())
    gif_b64 = "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
    pixel = (
        f'<img src="data:image/gif;base64,{gif_b64}" width="1" height="1" '
        f'alt="" style="display:block;width:1px;height:1px;border:0;" '
        f'data-track-id="{uid}"/>'
    )
    if "</body>" in html.lower():
        return re.sub(r"(</body>)", pixel + r"\1", html, count=1, flags=re.IGNORECASE)
    return html + pixel


# ============================================================
# Тема письма — только spintax (никаких zero-width!)
# ============================================================
def technique_subject(subject: str) -> str:
    return spin_text(subject)


# ============================================================
# AI rewrite (OpenAI-совместимые free-провайдеры + любой OpenAI endpoint)
# ============================================================
_FREE_AI_PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.1-8b-instant",
        "note": "Free: высокий лимит — https://console.groq.com",
    },
    "together": {
        "url": "https://api.together.xyz/v1/chat/completions",
        "model": "mistralai/Mistral-7B-Instruct-v0.3",
        "note": "Free credits на старте — https://api.together.ai",
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "mistralai/mistral-7b-instruct:free",
        "note": "Free-tier модели — https://openrouter.ai",
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
        "note": "Платный, лучшее качество — https://platform.openai.com",
    },
}


def ai_rephrase(
    html: str,
    api_key: str,
    provider: str = "groq",
    timeout: int = 45,
) -> Tuple[str, str]:
    """Переформулирует видимый текст письма через ИИ, сохраняя HTML-разметку.

    Returns: (rewritten_html, error_msg). error_msg == "" при успехе.
    Никогда не бросает исключение — при ошибке возвращает исходный html + текст ошибки.
    """
    cfg = _FREE_AI_PROVIDERS.get(provider)
    if not cfg:
        return html, f"Неизвестный провайдер: {provider}"
    if not api_key or not api_key.strip():
        return html, "Не задан API-ключ"

    import json as _json

    prompt = (
        "Rephrase the VISIBLE TEXT of this HTML email so it reads naturally but "
        "differs from the original (to improve deliverability). STRICT RULES:\n"
        "1. Keep ALL HTML tags, attributes, CSS, links and structure byte-for-byte.\n"
        "2. Only change human-readable text between tags. Do NOT add hidden text, "
        "zero-width characters, homoglyphs or invisible spans.\n"
        "3. Keep the same language as the original.\n"
        "4. Preserve placeholders like {{first_name}} exactly.\n"
        "Return ONLY the modified HTML, nothing else.\n\n"
        + html[:12000]
    )

    body = _json.dumps({
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": "You are an expert email deliverability specialist."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 4096,
        "temperature": 0.7,
    }).encode()

    req = urllib.request.Request(
        cfg["url"],
        data=body,
        headers={
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = _json.loads(resp.read().decode())
        result = data["choices"][0]["message"]["content"].strip()
        if "```" in result:
            m = re.search(r"```(?:html)?\n?(.*?)```", result, re.DOTALL)
            if m:
                result = m.group(1).strip()
        if not result:
            return html, "Пустой ответ от ИИ"
        return result, ""
    except urllib.error.HTTPError as e:
        body_err = e.read().decode(errors="replace")[:200]
        return html, f"HTTP {e.code}: {body_err}"
    except Exception as e:
        return html, str(e)


# ============================================================
# Реестр техник + apply_all
# ============================================================
# Техники, работающие по текстовым узлам (безопасны для структуры).
_TEXT_TECHNIQUES = {"spintax", "nbsp"}

_TECHNIQUE_FNS = {
    "spintax": technique_spintax,
    "nbsp": technique_nbsp,
    "data_attrs": technique_data_attrs,
    "random_comments": technique_random_comments,
    "css_micro": technique_css_micro,
    "css_custom_props": technique_css_custom_props,
    "font_stack": technique_font_stack,
    "uuid_fingerprint": technique_uuid_fingerprint,
    "tracking_pixel": technique_tracking_pixel,
}

ALL_TECHNIQUES = [
    "spintax", "nbsp", "data_attrs", "random_comments",
    "css_micro", "css_custom_props", "font_stack", "uuid_fingerprint", "tracking_pixel",
]

TECHNIQUE_LABELS = {
    "spintax": "Spintax {вариант1|вариант2} — реальная вариация текста",
    "nbsp": "Неразрывные пробелы после пунктуации",
    "data_attrs": "data-* атрибуты (отпечаток, безопасно)",
    "random_comments": "Доброкачественные HTML-комментарии",
    "css_micro": "CSS микро-вариации цвета (±1)",
    "css_custom_props": "CSS custom properties (отпечаток)",
    "font_stack": "Перестановка порядка font-family",
    "uuid_fingerprint": "UUID fingerprint (meta + CSS var, уникален на каждое письмо)",
    "tracking_pixel": "Tracking pixel (1×1, опционально)",
}

# По умолчанию — только безопасные для «Входящих»; tracking_pixel выключен.
DEFAULT_TECHNIQUES = [
    "spintax", "nbsp", "data_attrs", "random_comments",
    "css_micro", "css_custom_props", "font_stack", "uuid_fingerprint",
]


def apply_all(
    html: str,
    subject: str = "",
    techniques: Optional[List[str]] = None,
    seed: Optional[int] = None,
) -> Tuple[str, str]:
    """Применяет выбранные техники уникализации. Возвращает (html, subject).

    Гарантирует HTML-безопасность: текстовые техники меняют только текстовые
    узлы; структурные техники добавляют корректные теги/атрибуты. Никогда не
    бросает исключение.
    """
    if seed is not None:
        random.seed(seed)
    else:
        random.seed()

    chosen = techniques if techniques is not None else DEFAULT_TECHNIQUES
    for name in chosen:
        fn = _TECHNIQUE_FNS.get(name)
        if not fn:
            continue
        try:
            html = fn(html)
        except Exception:
            pass

    if subject:
        subject = technique_subject(subject)

    return html, subject

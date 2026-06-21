"""
FMailSender Email Uniqueizer v1.0.0
16 техник уникализации письма для обхода спам-фильтров без ИИ.
Также поддерживает бесплатные ИИ-API: Groq, Together.ai, OpenRouter (free models).
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

# Homoglyph tables: Latin -> Cyrillic look-alikes
_L2C: Dict[str, str] = {
    'a': '\u0430', 'e': '\u0435', 'o': '\u043e', 'p': '\u0440',
    'c': '\u0441', 'x': '\u0445', 'A': '\u0410', 'B': '\u0412',
    'C': '\u0421', 'E': '\u0415', 'H': '\u041d', 'K': '\u041a',
    'M': '\u041c', 'O': '\u041e', 'P': '\u0420', 'T': '\u0422',
    'X': '\u0425', 'Y': '\u0423',
}

# Zero-width characters
_ZWC = [
    '\u200b',  # Zero Width Space
    '\u200c',  # Zero Width Non-Joiner
    '\u200d',  # Zero Width Joiner
    '\u2060',  # Word Joiner
    '\ufeff',  # Zero Width No-Break Space
    '\u00ad',  # Soft Hyphen
]

_LEGIT_WORDS = [
    "confirmation", "notification", "update", "message", "delivery",
    "secure", "verified", "account", "service", "system", "official",
    "information", "support", "customer", "details", "request",
    "transaction", "reference", "portal", "helpdesk",
]

_FREE_AI_PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama3-8b-8192",
        "note": "Free: 14400 req/day — https://console.groq.com",
    },
    "together": {
        "url": "https://api.together.xyz/v1/chat/completions",
        "model": "mistralai/Mistral-7B-Instruct-v0.3",
        "note": "Free: $25 credits on signup — https://api.together.ai",
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "mistralai/mistral-7b-instruct:free",
        "note": "Free tier models — https://openrouter.ai",
    },
}


def _rid(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def _hash12() -> str:
    return hashlib.md5(uuid.uuid4().bytes).hexdigest()[:12]


# ============================================================
# Technique 1: Zero-width characters between words
# ============================================================
def technique_zero_width(html: str, intensity: float = 0.35) -> str:
    """Вставляет невидимые символы нулевой ширины между словами."""
    def _inject(m: re.Match) -> str:
        text = m.group(0)
        if len(text) < 4:
            return text
        parts = text.split(" ")
        out = []
        for i, w in enumerate(parts):
            out.append(w)
            if i < len(parts) - 1:
                if random.random() < intensity:
                    out.append(random.choice(_ZWC))
                out.append(" ")
        return "".join(out)
    return re.sub(r"(?<=>)[^<]+(?=<)", _inject, html)


# ============================================================
# Technique 2: Homoglyph substitution (Latin -> Cyrillic)
# ============================================================
def technique_homoglyphs(html: str, ratio: float = 0.12) -> str:
    """Заменяет часть латинских букв на кириллические двойники."""
    def _sub(m: re.Match) -> str:
        return "".join(
            _L2C[ch] if ch in _L2C and random.random() < ratio else ch
            for ch in m.group(0)
        )
    return re.sub(r"(?<=>)[^<]+(?=<)", _sub, html)


# ============================================================
# Technique 3: HTML entity encoding of random chars
# ============================================================
def technique_html_entities(html: str, ratio: float = 0.08) -> str:
    """Кодирует часть символов как HTML-сущности (&#65; = A)."""
    def _encode(m: re.Match) -> str:
        out = []
        for ch in m.group(0):
            if ch.isalpha() and random.random() < ratio:
                code = ord(ch)
                out.append(f"&#{code};" if random.random() < 0.5 else f"&#x{code:x};")
            else:
                out.append(ch)
        return "".join(out)
    return re.sub(r"(?<=>)[^<]+(?=<)", _encode, html)


# ============================================================
# Technique 4: Invisible spans (display:none / opacity:0)
# ============================================================
def technique_invisible_spans(html: str, count: int = 6) -> str:
    """Вставляет невидимые <span> с рандомными словами."""
    spans = []
    for _ in range(count):
        word = random.choice(_LEGIT_WORDS)
        uid = _rid(6)
        spans.append(
            f'<span style="font-size:0px;line-height:0px;color:transparent;'
            f'display:inline;opacity:0;" aria-hidden="true" data-uid="{uid}">{word}</span>'
        )
    tags = list(re.finditer(r"</(td|p|div|li|span)>", html, re.IGNORECASE))
    for span in spans:
        if tags:
            t = random.choice(tags)
            html = html[:t.end()] + span + html[t.end():]
    return html


# ============================================================
# Technique 5: Random HTML comments
# ============================================================
def technique_random_comments(html: str, count: int = 4) -> str:
    """Вставляет случайные HTML-комментарии с хешами."""
    tags = list(re.finditer(r"</(td|p|div|tr|table)>", html, re.IGNORECASE))
    for _ in range(count):
        comment = f"<!-- {_hash12()} -->"
        if tags:
            t = random.choice(tags)
            html = html[:t.end()] + comment + html[t.end():]
    return html


# ============================================================
# Technique 6: Random data-* attributes on block tags
# ============================================================
def technique_data_attrs(html: str, ratio: float = 0.6) -> str:
    """Добавляет случайные data-атрибуты к блочным тегам."""
    def _add(m: re.Match) -> str:
        if random.random() > ratio:
            return m.group(0)
        tag = m.group(0)
        uid = _rid(8)
        ts = random.randint(1_000_000, 9_999_999)
        return tag[:-1] + f' data-mid="{uid}" data-ts="{ts}">'
    return re.sub(r"<(td|tr|div|p|table|tbody)[^>]*>", _add, html, flags=re.IGNORECASE)


# ============================================================
# Technique 7: CSS micro-variation (color shift +/-1, unique meta)
# ============================================================
def technique_css_micro(html: str) -> str:
    """Смещает цвета на ±1 и добавляет уникальный meta-тег."""
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

    html = re.sub(r"#([0-9a-fA-F]{6})\b", _vary, html)
    html = re.sub(r"(<head[^>]*>)", r"\1" + marker, html, flags=re.IGNORECASE)
    return html


# ============================================================
# Technique 8: Tracking pixel (data URI, unique UUID)
# ============================================================
def technique_tracking_pixel(html: str) -> str:
    """Добавляет 1x1 tracking pixel с уникальным UUID (data URI)."""
    uid = str(uuid.uuid4())
    gif_b64 = "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
    pixel = (
        f'<img src="data:image/gif;base64,{gif_b64}" width="1" height="1" '
        f'alt="" style="display:block;width:1px;height:1px;border:0;" '
        f'data-track-id="{uid}" />'
    )
    if "</body>" in html.lower():
        html = re.sub(r"(</body>)", pixel + r"\1", html, flags=re.IGNORECASE)
    else:
        html += pixel
    return html


# ============================================================
# Technique 9: Word-level span wrapping
# ============================================================
def technique_word_spans(html: str, ratio: float = 0.08) -> str:
    """Оборачивает часть слов в <span data-w=uid>."""
    def _wrap(m: re.Match) -> str:
        parts = re.split(r"(\s+)", m.group(0))
        out = []
        for part in parts:
            if part.strip() and random.random() < ratio:
                out.append(f'<span data-w="{_rid(4)}">{part}</span>')
            else:
                out.append(part)
        return "".join(out)
    return re.sub(r"(?<=>)[^<]{5,}(?=<)", _wrap, html)


# ============================================================
# Technique 10: Non-breaking spaces after punctuation
# ============================================================
def technique_nbsp(html: str, ratio: float = 0.25) -> str:
    """Вставляет &nbsp; после знаков препинания случайным образом."""
    def _inject(m: re.Match) -> str:
        text = m.group(0)
        out = []
        for i, ch in enumerate(text):
            out.append(ch)
            if ch in ".!?,:;" and i < len(text) - 1 and text[i + 1] == " " and random.random() < ratio:
                out.append("&nbsp;")
        return "".join(out)
    return re.sub(r"(?<=>)[^<]+(?=<)", _inject, html)


# ============================================================
# Technique 11: Soft hyphens in long words
# ============================================================
def technique_soft_hyphens(html: str, ratio: float = 0.06) -> str:
    """Вставляет мягкие переносы (U+00AD) в длинные слова."""
    SHY = "\u00ad"

    def _inject(m: re.Match) -> str:
        parts = re.split(r"(\s+)", m.group(0))
        out = []
        for w in parts:
            if len(w) > 9 and random.random() < ratio:
                mid = len(w) // 2
                w = w[:mid] + SHY + w[mid:]
            out.append(w)
        return "".join(out)
    return re.sub(r"(?<=>)[^<]+(?=<)", _inject, html)


# ============================================================
# Technique 12: Hidden text (white on white, height 1px)
# ============================================================
def technique_hidden_text(html: str, count: int = 3) -> str:
    """Добавляет скрытые текстовые блоки (белый на белом)."""
    snippets = []
    for _ in range(count):
        words = random.sample(_LEGIT_WORDS, k=random.randint(2, 4))
        snippets.append(
            f'<div style="color:#ffffff;background:#ffffff;font-size:1px;'
            f'line-height:1px;max-height:1px;overflow:hidden;opacity:0;" '
            f'aria-hidden="true" data-h="{_rid(6)}">{" ".join(words)}</div>'
        )
    body_m = re.search(r"<body[^>]*>", html, re.IGNORECASE)
    if body_m:
        pos = body_m.end()
        html = html[:pos] + "".join(snippets) + html[pos:]
    return html


# ============================================================
# Technique 13: Font-family stack shuffle
# ============================================================
def technique_font_stack(html: str) -> str:
    """Перемешивает порядок шрифтов в font-family."""
    def _shuffle(m: re.Match) -> str:
        raw = m.group(1)
        fonts = [f.strip().strip("'\"") for f in raw.split(',')]
        if len(fonts) > 2:
            generic = fonts[-1]
            specific = fonts[:-1]
            random.shuffle(specific)
            return "font-family: " + ", ".join(specific + [generic])
        return m.group(0)
    return re.sub(r"font-family:\s*([^;"}{]+)", _shuffle, html)


# ============================================================
# Technique 14: Unicode variation selectors (FE00-FE02)
# ============================================================
def technique_unicode_variation(html: str, ratio: float = 0.04) -> str:
    """Добавляет Unicode variation selectors к части символов."""
    VS = ["\ufe00", "\ufe01", "\ufe02"]

    def _inject(m: re.Match) -> str:
        out = []
        for ch in m.group(0):
            out.append(ch)
            if ch.isalpha() and ord(ch) < 128 and random.random() < ratio:
                out.append(random.choice(VS))
        return "".join(out)
    return re.sub(r"(?<=>)[^<]+(?=<)", _inject, html)


# ============================================================
# Technique 15: CSS custom properties as unique fingerprint
# ============================================================
def technique_css_custom_props(html: str) -> str:
    """Добавляет CSS custom properties с уникальными значениями."""
    uid = _rid(16)
    ts = random.randint(1_000_000, 9_999_999)
    style = f'<style>:root{{--x-uid:"{uid}";--x-ts:"{ts}"}}</style>'
    if "</head>" in html.lower():
        html = re.sub(r"(</head>)", style + r"\1", html, flags=re.IGNORECASE)
    else:
        html = style + html
    return html


# ============================================================
# Technique 16: Subject line zero-width injection
# ============================================================
def technique_subject(subject: str, intensity: float = 0.4) -> str:
    """Вставляет невидимые символы в тему письма."""
    words = subject.split(" ")
    out = []
    for i, w in enumerate(words):
        out.append(w)
        if i < len(words) - 1:
            if random.random() < intensity:
                out.append(random.choice(["\u200b", "\u200c", "\u2060"]))
            out.append(" ")
    return "".join(out)


# ============================================================
# AI Rewrite via free API (Groq / Together.ai / OpenRouter)
# ============================================================
def ai_rephrase(
    html: str,
    api_key: str,
    provider: str = "groq",
    timeout: int = 45,
) -> Tuple[str, str]:
    """
    Перефразирует текст письма через бесплатный ИИ-API.

    Бесплатные провайдеры:
      groq       - https://console.groq.com  (14400 req/day бесплатно)
      together   - https://api.together.ai   ($25 кредитов при регистрации)
      openrouter - https://openrouter.ai     (free-tier модели mistral/gemma)

    Returns: (rewritten_html, error_msg). error_msg == "" on success.
    """
    cfg = _FREE_AI_PROVIDERS.get(provider)
    if not cfg:
        return html, f"Неизвестный провайдер: {provider}"

    import json as _json

    prompt = (
        "Rephrase this HTML email to bypass spam filters. "
        "Keep ALL HTML tags, CSS and structure exactly as is. "
        "Only change visible text content between tags. "
        "Return ONLY the modified HTML, nothing else.\n\n"
        + html[:8000]
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
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = _json.loads(resp.read().decode())
        result = data["choices"][0]["message"]["content"].strip()
        # Extract HTML if wrapped in markdown code block
        if "```" in result:
            m = re.search(r"```(?:html)?\n?(.*?)```", result, re.DOTALL)
            if m:
                result = m.group(1).strip()
        return result, ""
    except urllib.error.HTTPError as e:
        body_err = e.read().decode(errors="replace")[:200]
        return html, f"HTTP {e.code}: {body_err}"
    except Exception as e:
        return html, str(e)


# ============================================================
# Master labels and apply function
# ============================================================

ALL_TECHNIQUES = [
    "zero_width", "homoglyphs", "html_entities", "invisible_spans",
    "random_comments", "data_attrs", "css_micro", "tracking_pixel",
    "word_spans", "nbsp", "soft_hyphens", "hidden_text",
    "font_stack", "unicode_variation", "css_custom_props",
]

TECHNIQUE_LABELS = {
    "zero_width": "Символы нулевой ширины (ZWC)",
    "homoglyphs": "Гомоглифы латиница/кириллица",
    "html_entities": "HTML-сущности (&#65; = A)",
    "invisible_spans": "Невидимые <span> со словами",
    "random_comments": "Случайные HTML-комментарии",
    "data_attrs": "data-* атрибуты (fingerprint)",
    "css_micro": "CSS микро-вариации (±1 цвет)",
    "tracking_pixel": "Tracking pixel (UUID data URI)",
    "word_spans": "Обёртка слов в <span>",
    "nbsp": "Неразрывные пробелы после знаков",
    "soft_hyphens": "Мягкие переносы в длинных словах",
    "hidden_text": "Скрытый белый текст",
    "font_stack": "Перемешивание font-family",
    "unicode_variation": "Unicode variation selectors",
    "css_custom_props": "CSS custom properties (fingerprint)",
}

_TECHNIQUE_FNS = {
    "zero_width": technique_zero_width,
    "homoglyphs": technique_homoglyphs,
    "html_entities": technique_html_entities,
    "invisible_spans": technique_invisible_spans,
    "random_comments": technique_random_comments,
    "data_attrs": technique_data_attrs,
    "css_micro": technique_css_micro,
    "tracking_pixel": technique_tracking_pixel,
    "word_spans": technique_word_spans,
    "nbsp": technique_nbsp,
    "soft_hyphens": technique_soft_hyphens,
    "hidden_text": technique_hidden_text,
    "font_stack": technique_font_stack,
    "unicode_variation": technique_unicode_variation,
    "css_custom_props": technique_css_custom_props,
}

# Safe default set (do not break rendering)
DEFAULT_TECHNIQUES = [
    "zero_width", "invisible_spans", "random_comments", "data_attrs",
    "css_micro", "tracking_pixel", "nbsp", "soft_hyphens",
    "hidden_text", "css_custom_props",
]


def apply_all(
    html: str,
    subject: str = "",
    techniques: Optional[List[str]] = None,
    seed: Optional[int] = None,
) -> Tuple[str, str]:
    """
    Применяет выбранные техники уникализации.
    Возвращает (новый_html, новая_тема).
    Никогда не бросает исключение.
    """
    if seed is not None:
        random.seed(seed)
    else:
        random.seed()

    chosen = techniques if techniques is not None else DEFAULT_TECHNIQUES
    for name in chosen:
        fn = _TECHNIQUE_FNS.get(name)
        if fn:
            try:
                html = fn(html)
            except Exception:
                pass

    if subject:
        subject = technique_subject(subject)

    return html, subject
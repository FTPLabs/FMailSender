"""
Анализатор контента писем на спам. Score 0-100 с разбивкой по категориям.
База 500+ спам-триггеров. Проверка Image-to-Text ratio, HTML-валидация.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple
import dns.resolver

# ──────────────────────────────────────────────
# База спам-слов (расширяется из spam_words.json)
# ──────────────────────────────────────────────

DEFAULT_SPAM_WORDS = [
    # Финансы/деньги
    "free money", "cash bonus", "earn money fast", "make money online",
    "guaranteed income", "financial freedom", "no investment", "passive income",
    "risk free", "risk-free", "double your money", "extra income",
    "work from home", "be your own boss", "quit your job",
    # Кликбейт
    "click here", "click now", "act now", "limited time", "hurry up",
    "don't wait", "order now", "buy now", "apply now", "subscribe now",
    "call now", "visit now", "sign up free", "join for free",
    # Бесплатно
    "100% free", "absolutely free", "completely free", "totally free",
    "free access", "free trial", "free gift", "free prize", "free offer",
    "free consultation", "free demo", "free membership", "free sample",
    # Срочность
    "urgent", "immediately", "as soon as possible", "don't delete",
    "important notice", "final notice", "last chance", "expire", "expires",
    "deadline", "today only", "this week only", "limited offer",
    # Гарантии
    "100% guaranteed", "satisfaction guaranteed", "money back guarantee",
    "no questions asked", "risk free guarantee", "no risk", "iron clad",
    # Медицина/похудение
    "lose weight", "weight loss", "burn fat", "miracle cure", "cure",
    "treatment", "medicine", "pharmacy", "prescription", "pills", "diet",
    "amazing results", "incredible results", "guaranteed results",
    # Казино/азартные игры
    "casino", "jackpot", "lottery", "winner", "you won", "congratulations you",
    "lucky winner", "selected winner", "prize winner",
    # Взрослый контент
    "adult", "xxx", "sex", "erotic", "dating", "singles",
    # Спам-фразы
    "this is not spam", "this is not junk", "remove me", "unsubscribe here",
    "opt out", "no longer receive", "dear friend", "dear homeowner",
    "dear valued customer", "valued customer",
    # Маркетинг
    "best price", "lowest price", "cheapest", "discount", "sale", "special offer",
    "amazing deal", "incredible deal", "unbeatable deal", "promo",
    "promotion", "coupon", "voucher",
    # Технические признаки
    "http://", "www.", "click the link", "see below", "see above",
    "this email was sent", "if you received this in error",
    # Русские спам-слова
    "бесплатно", "скидка", "акция", "подарок", "выиграй", "победитель",
    "срочно", "спешите", "только сегодня", "ограниченное предложение",
    "гарантировано", "доход", "заработок", "кредит", "займ", "казино",
]


@dataclass
class SpamCheckResult:
    """Результат проверки содержимого на спам."""
    score: int                      # 0 (чистый) — 100 (спам)
    is_spam: bool                   # score >= 70
    categories: dict = field(default_factory=dict)
    triggered_words: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    @property
    def grade(self) -> str:
        if self.score <= 20:
            return "Отлично"
        elif self.score <= 40:
            return "Хорошо"
        elif self.score <= 60:
            return "Удовлетворительно"
        elif self.score <= 80:
            return "Плохо"
        return "Спам"

    @property
    def grade_color(self) -> str:
        if self.score <= 20:
            return "#22c55e"   # зелёный
        elif self.score <= 40:
            return "#84cc16"   # жёлто-зелёный
        elif self.score <= 60:
            return "#f59e0b"   # жёлтый
        elif self.score <= 80:
            return "#ef4444"   # оранжевый
        return "#dc2626"       # красный


# ──────────────────────────────────────────────
# Анализатор
# ──────────────────────────────────────────────

class SpamChecker:
    """Анализирует содержимое письма и возвращает spam score."""

    def __init__(self, spam_words_file: Optional[Path] = None):
        self.spam_words = list(DEFAULT_SPAM_WORDS)
        if spam_words_file and spam_words_file.exists():
            try:
                with open(spam_words_file, "r", encoding="utf-8") as f:
                    extra = json.load(f)
                    self.spam_words.extend(extra)
            except Exception:
                pass

        # Компилируем паттерны для быстрого поиска
        self._patterns = [
            (word, re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE))
            for word in self.spam_words
        ]

    def check(
        self,
        subject: str,
        body_html: str,
        body_text: str = "",
        from_address: str = "",
    ) -> SpamCheckResult:
        """
        Выполняет полную проверку письма.
        Возвращает SpamCheckResult с детальной разбивкой.
        """
        total_score = 0
        categories = {}
        triggered_words = []
        issues = []
        suggestions = []

        # ── 1. Спам-слова в теме (вес 3) ─────────────────
        subject_score = 0
        for word, pattern in self._patterns:
            if pattern.search(subject):
                subject_score += 3
                triggered_words.append(f"Тема: {word}")
        subject_score = min(subject_score, 30)
        categories["Спам-слова в теме"] = subject_score
        total_score += subject_score

        if "!!!" in subject or subject.isupper():
            issues.append("Тема содержит восклицательные знаки или написана заглавными")
            total_score += 5

        # ── 2. Спам-слова в теле (вес 2) ─────────────────
        content = body_text or _html_to_text(body_html)
        body_score = 0
        for word, pattern in self._patterns:
            if pattern.search(content):
                body_score += 2
                if word not in triggered_words:
                    triggered_words.append(f"Тело: {word}")
        body_score = min(body_score, 25)
        categories["Спам-слова в тексте"] = body_score
        total_score += body_score

        # ── 3. HTML-структура ─────────────────────────────
        html_score = 0

        if re.search(r"javascript:", body_html, re.IGNORECASE):
            html_score += 15
            issues.append("HTML содержит javascript: ссылки")
            suggestions.append("Уберите javascript: из href атрибутов")

        if re.search(r"display\s*:\s*none", body_html, re.IGNORECASE):
            html_score += 10
            issues.append("HTML содержит скрытый контент (display:none)")
            suggestions.append("Уберите скрытые элементы из HTML")

        hidden_div = re.search(r'<div[^>]+style="[^"]*visibility\s*:\s*hidden[^"]*"', body_html, re.IGNORECASE)
        if hidden_div:
            html_score += 8
            issues.append("HTML содержит невидимые div-блоки")

        # Слишком много ссылок
        link_count = len(re.findall(r"<a\s+", body_html, re.IGNORECASE))
        if link_count > 10:
            html_score += 5
            issues.append(f"Слишком много ссылок ({link_count})")
            suggestions.append("Уменьшите количество ссылок до 3-5")

        # Нет text/plain версии (проверяем по флагу)
        if not body_text and not _html_to_text(body_html).strip():
            html_score += 10
            issues.append("Нет text/plain версии письма")
            suggestions.append("Добавьте plain text версию письма")

        html_score = min(html_score, 20)
        categories["HTML-структура"] = html_score
        total_score += html_score

        # ── 4. Image-to-Text ratio ────────────────────────
        img_score = 0
        img_count = len(re.findall(r"<img\s+", body_html, re.IGNORECASE))
        text_len = len(_html_to_text(body_html).replace(" ", ""))

        if img_count > 0 and text_len < 200:
            img_score += 10
            issues.append("Мало текста относительно изображений")
            suggestions.append("Добавьте больше текстового контента (минимум 200 символов)")

        if img_count > 5:
            img_score += 5
            issues.append(f"Много изображений ({img_count})")
            suggestions.append("Используйте не более 3-4 изображений")

        img_score = min(img_score, 15)
        categories["Соотношение изображений/текста"] = img_score
        total_score += img_score

        # ── 5. Проверка заглавных букв ────────────────────
        caps_score = 0
        words_in_body = content.split()
        if words_in_body:
            caps_words = sum(1 for w in words_in_body if w.isupper() and len(w) > 2)
            caps_ratio = caps_words / len(words_in_body)
            if caps_ratio > 0.15:
                caps_score = min(int(caps_ratio * 50), 10)
                issues.append(f"Много слов в ВЕРХНЕМ РЕГИСТРЕ ({int(caps_ratio*100)}%)")
                suggestions.append("Уменьшите использование CAPS LOCK")

        categories["Заглавные буквы"] = caps_score
        total_score += caps_score

        total_score = min(total_score, 100)

        if not issues:
            suggestions.append("Письмо выглядит хорошо! Продолжайте в том же духе.")

        return SpamCheckResult(
            score=total_score,
            is_spam=total_score >= 70,
            categories=categories,
            triggered_words=triggered_words[:20],  # Ограничиваем вывод
            issues=issues,
            suggestions=suggestions,
        )


def _html_to_text(html: str) -> str:
    """Простая конвертация HTML → plain text."""
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    return text.strip()


# ──────────────────────────────────────────────
# SPF/DKIM/DMARC-подсказчик
# ──────────────────────────────────────────────

@dataclass
class DnsAuthStatus:
    """Статус DNS-аутентификации домена."""
    domain: str
    spf: Optional[str] = None
    dkim: Optional[str] = None      # selector._domainkey
    dmarc: Optional[str] = None
    spf_valid: bool = False
    dkim_valid: bool = False
    dmarc_valid: bool = False
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


def check_dns_auth(domain: str, dkim_selector: str = "default") -> DnsAuthStatus:
    """
    Выполняет DNS-проверку SPF, DKIM, DMARC для домена.
    Возвращает статус и рекомендации.
    """
    status = DnsAuthStatus(domain=domain)

    # ── SPF ──────────────────────────────────────
    try:
        answers = dns.resolver.resolve(domain, "TXT")
        for rdata in answers:
            txt = str(rdata).strip('"')
            if txt.startswith("v=spf1"):
                status.spf = txt
                status.spf_valid = True
                break
    except dns.exception.DNSException:
        pass

    if not status.spf_valid:
        status.issues.append("SPF-запись не найдена")
        status.suggestions.append(
            f'Добавьте TXT-запись для {domain}:\n'
            f'v=spf1 include:_spf.{domain} ~all'
        )

    # ── DKIM ─────────────────────────────────────
    dkim_host = f"{dkim_selector}._domainkey.{domain}"
    try:
        answers = dns.resolver.resolve(dkim_host, "TXT")
        for rdata in answers:
            txt = str(rdata).strip('"')
            if "v=DKIM1" in txt or "p=" in txt:
                status.dkim = txt[:100] + "..." if len(txt) > 100 else txt
                status.dkim_valid = True
                break
    except dns.exception.DNSException:
        pass

    if not status.dkim_valid:
        status.issues.append(f"DKIM-запись не найдена (селектор: {dkim_selector})")
        status.suggestions.append(
            f"Настройте DKIM-подпись в вашем почтовом сервере и добавьте TXT-запись:\n"
            f"{dkim_selector}._domainkey.{domain}  →  v=DKIM1; k=rsa; p=<ваш_публичный_ключ>"
        )

    # ── DMARC ────────────────────────────────────
    dmarc_host = f"_dmarc.{domain}"
    try:
        answers = dns.resolver.resolve(dmarc_host, "TXT")
        for rdata in answers:
            txt = str(rdata).strip('"')
            if txt.startswith("v=DMARC1"):
                status.dmarc = txt
                status.dmarc_valid = True
                break
    except dns.exception.DNSException:
        pass

    if not status.dmarc_valid:
        status.issues.append("DMARC-политика не настроена")
        status.suggestions.append(
            f'Добавьте TXT-запись для _dmarc.{domain}:\n'
            f'v=DMARC1; p=none; rua=mailto:dmarc@{domain}'
        )

    return status


# ──────────────────────────────────────────────
# Валидация email-адреса
# ──────────────────────────────────────────────

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*"
    r"\.[a-zA-Z]{2,}$"
)


def validate_email_format(email_addr: str) -> bool:
    """Проверяет формат email через regex."""
    return bool(EMAIL_REGEX.match(email_addr.strip()))


def validate_email_mx(email_addr: str) -> Tuple[bool, str]:
    """
    Проверяет существование MX-записи домена.
    Возвращает (valid, message).
    """
    if not validate_email_format(email_addr):
        return False, "Неверный формат email"

    domain = email_addr.split("@")[1]
    try:
        mx_records = dns.resolver.resolve(domain, "MX")
        if mx_records:
            return True, f"MX: {str(mx_records[0].exchange).rstrip('.')}"
    except dns.resolver.NXDOMAIN:
        return False, "Домен не существует"
    except dns.resolver.NoAnswer:
        # Нет MX, но может быть A-запись
        try:
            dns.resolver.resolve(domain, "A")
            return True, "Нет MX-записи, но домен существует"
        except Exception:
            return False, "Нет MX-записи для домена"
    except dns.exception.DNSException as e:
        return False, f"Ошибка DNS: {str(e)}"
    except Exception as e:
        return False, f"Ошибка проверки: {str(e)}"

    return False, "Неизвестная ошибка"

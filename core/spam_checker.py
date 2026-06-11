"""
Анализатор контента писем на спам. Score 0-100 с разбивкой по категориям.
База 500+ спам-триггеров. Проверка Image-to-Text ratio, HTML-валидация.
validate_email_format импортируется из sender.py (единственный источник истины).
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import dns.resolver
    import dns.exception
    _DNS_AVAILABLE = True
except ImportError:
    _DNS_AVAILABLE = False

# FIX: импортируем validate_email_format из sender (единственный источник истины)
from core.sender import validate_email_format

DEFAULT_SPAM_WORDS = [
    "free money", "cash bonus", "earn money fast", "make money online",
    "guaranteed income", "financial freedom", "no investment", "passive income",
    "risk free", "risk-free", "double your money", "extra income",
    "work from home", "be your own boss", "quit your job",
    "click here", "click now", "act now", "limited time", "hurry up",
    "don't wait", "order now", "buy now", "apply now", "subscribe now",
    "call now", "visit now", "sign up free", "join for free",
    "100% free", "absolutely free", "completely free", "totally free",
    "free access", "free trial", "free gift", "free prize", "free offer",
    "free consultation", "free demo", "free membership", "free sample",
    "urgent", "immediately", "as soon as possible", "don't delete",
    "important notice", "final notice", "last chance", "expire", "expires",
    "deadline", "today only", "this week only", "limited offer",
    "100% guaranteed", "satisfaction guaranteed", "money back guarantee",
    "no questions asked", "risk free guarantee", "no risk",
    "lose weight", "weight loss", "burn fat", "miracle cure", "cure",
    "treatment", "medicine", "pharmacy", "prescription", "pills", "diet",
    "amazing results", "incredible results", "guaranteed results",
    "casino", "jackpot", "lottery", "winner", "you won", "congratulations you",
    "lucky winner", "selected winner", "prize winner",
    "this is not spam", "this is not junk", "remove me", "unsubscribe here",
    "opt out", "no longer receive", "dear friend", "dear homeowner",
    "dear valued customer", "valued customer",
    "best price", "lowest price", "cheapest", "discount", "sale", "special offer",
    "amazing deal", "incredible deal", "unbeatable deal", "promo",
    "бесплатно", "деньги", "заработок", "быстрые деньги", "пассивный доход",
    "срочно", "только сегодня", "ограниченное предложение",
]


@dataclass
class SpamCheckResult:
    score: int = 0
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    passed: List[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    @property
    def verdict(self) -> str:
        if self.score < 20:
            return "✅ Хороший"
        elif self.score < 50:
            return "⚠️ Подозрительный"
        else:
            return "🚫 Спам"

    @property
    def is_clean(self) -> bool:
        return self.score < 30


class SpamChecker:
    def __init__(self, spam_words_path: Optional[Path] = None):
        self._spam_words = list(DEFAULT_SPAM_WORDS)
        if spam_words_path and spam_words_path.exists():
            try:
                with open(spam_words_path, "r", encoding="utf-8") as f:
                    extra = json.load(f)
                    if isinstance(extra, list):
                        self._spam_words.extend(extra)
            except Exception:
                pass

    def check(self, subject: str, body_html: str, sender_email: str = "") -> SpamCheckResult:
        result = SpamCheckResult()
        body_text = self._strip_html(body_html)
        combined = (subject + " " + body_text).lower()

        # ── Спам-слова ───────────────────────────────────────────────────
        spam_found = []
        for word in self._spam_words:
            if word.lower() in combined:
                spam_found.append(word)
        if spam_found:
            score = min(len(spam_found) * 5, 40)
            result.score += score
            result.issues.append(f"Спам-слова ({len(spam_found)}): {', '.join(spam_found[:5])}")
        else:
            result.passed.append("Нет спам-слов")
        result.details["spam_words_found"] = spam_found

        # ── Заглавные буквы ──────────────────────────────────────────────
        words = subject.split()
        caps_count = sum(1 for w in words if len(w) > 2 and w.isupper())
        if len(words) > 0 and caps_count / max(len(words), 1) > 0.4:
            result.score += 10
            result.issues.append("Слишком много ЗАГЛАВНЫХ букв в теме")
        else:
            result.passed.append("Нормальный регистр темы")

        # ── Восклицательные знаки ────────────────────────────────────────
        exclaim_count = subject.count("!") + body_text.count("!")
        if exclaim_count > 5:
            result.score += min(exclaim_count * 2, 15)
            result.warnings.append(f"Много восклицательных знаков: {exclaim_count}")
        else:
            result.passed.append("Допустимое количество !")

        # ── Image-to-Text ratio ──────────────────────────────────────────
        img_count = len(re.findall(r"<img", body_html, re.IGNORECASE))
        text_len = len(body_text.strip())
        if img_count > 0 and text_len < 100:
            result.score += 15
            result.warnings.append("Мало текста относительно изображений")
        elif img_count == 0 and text_len > 50:
            result.passed.append("Хороший Image-to-Text баланс")

        # ── HTML-структура ───────────────────────────────────────────────
        if not re.search(r"<html", body_html, re.IGNORECASE):
            result.warnings.append("Отсутствует тег <html>")
        if not re.search(r"unsubscribe|отписаться", combined):
            result.warnings.append("Нет ссылки отписки")
            result.score += 5
        else:
            result.passed.append("Есть ссылка отписки")

        # ── URL в теме ───────────────────────────────────────────────────
        if re.search(r"https?://", subject):
            result.score += 10
            result.issues.append("URL в теме письма")

        # ── Проверка отправителя ─────────────────────────────────────────
        if sender_email:
            if not validate_email_format(sender_email):
                result.score += 20
                result.issues.append("Невалидный email отправителя")
            else:
                domain = sender_email.split("@")[-1].lower()
                if _DNS_AVAILABLE:
                    self._check_dns(domain, result)
                result.passed.append("Email отправителя валиден")

        result.score = min(result.score, 100)
        return result

    def _check_dns(self, domain: str, result: SpamCheckResult) -> None:
        """Проверяет MX и SPF записи домена."""
        # MX check
        try:
            dns.resolver.resolve(domain, "MX")
            result.passed.append("MX запись найдена")
        except dns.resolver.NXDOMAIN:
            result.score += 20
            result.issues.append(f"Домен не существует: {domain}")
            return
        except dns.resolver.NoAnswer:
            result.warnings.append(f"MX запись отсутствует для: {domain}")
        except Exception:
            pass

        # SPF check — FIX: отдельный except для каждого типа ошибки DNS
        try:
            txt_records = dns.resolver.resolve(domain, "TXT")
            spf_found = any(
                "v=spf1" in str(r) for r in txt_records
            )
            if spf_found:
                result.passed.append("SPF запись найдена")
            else:
                result.warnings.append("SPF запись не найдена")
                result.score += 5
        except dns.resolver.NoAnswer:
            result.warnings.append("TXT записей нет (SPF не проверить)")
        except dns.resolver.NXDOMAIN:
            pass
        except Exception:
            pass

        # A-record fallback
        try:
            dns.resolver.resolve(domain, "A")
            result.passed.append("A-запись домена найдена")
        except dns.resolver.NoAnswer:
            result.warnings.append("A-запись отсутствует")
        except Exception:
            pass

    def _strip_html(self, html_str: str) -> str:
        text = re.sub(r"<[^>]+>", "", html_str)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def get_recommendations(self, result: SpamCheckResult) -> List[str]:
        recs = []
        if result.score >= 50:
            recs.append("⚠️ Высокий spam score — письмо может попасть в спам")
        for issue in result.issues:
            if "спам-слов" in issue.lower():
                recs.append("Уберите спам-триггеры из текста письма")
            elif "заглавн" in issue.lower():
                recs.append("Используйте нормальный регистр в теме письма")
            elif "url в теме" in issue.lower():
                recs.append("Не размещайте URL прямо в теме письма")
        if not result.issues:
            recs.append("✅ Письмо выглядит чисто — хорошие шансы на доставку")
        return recs

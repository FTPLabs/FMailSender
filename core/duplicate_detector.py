"""
FMailSender Duplicate Detector v1.1.0 — fast deduplication for email/recipient lists.
FIX v1.1.0: добавлены outlook.co.uk/jp, live.ru, hotmail.ru/es/it, internet.ru, ro.ru в alias-группы.

Features:
- Case-insensitive deduplication (alice@EXAMPLE.COM == alice@example.com)
- Sub-addressing strip: alice+tag@example.com → alice@example.com (optional)
- Domain alias collapse: googlemail.com ↔ gmail.com, etc.
- Returns: unique emails, duplicate indices, stats dict
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

# ── Known domain aliases ─────────────────────────────────────────────────────
_DOMAIN_ALIAS_GROUPS: list[FrozenSet[str]] = [
    frozenset({"gmail.com", "googlemail.com"}),
    frozenset({"hotmail.com", "hotmail.co.uk", "hotmail.fr", "hotmail.de",
               "hotmail.ru", "hotmail.es", "hotmail.it", "msn.com"}),
    frozenset({"outlook.com", "outlook.fr", "outlook.de", "outlook.es",
               "outlook.it", "outlook.ru", "outlook.co.uk", "outlook.jp",
               "live.com", "live.co.uk", "live.fr", "live.de", "live.ru",
               "hotmail.ru", "hotmail.es", "hotmail.it", "windowslive.com"}),
    frozenset({"yandex.ru", "yandex.com", "ya.ru", "yandex.kz",
               "yandex.by", "yandex.ua"}),
    frozenset({"mail.ru", "bk.ru", "list.ru", "inbox.ru", "internet.ru", "ro.ru"}),
    frozenset({"protonmail.com", "proton.me", "protonmail.ch", "pm.me"}),
    frozenset({"icloud.com", "me.com", "mac.com"}),
]
_DOMAIN_TO_CANONICAL: Dict[str, str] = {}
for _grp in _DOMAIN_ALIAS_GROUPS:
    _canon = sorted(_grp)[0]
    for _d in _grp:
        _DOMAIN_TO_CANONICAL[_d] = _canon


@dataclass
class DedupResult:
    unique_emails: List[str]
    duplicate_indices: List[int]          # 0-based indices of duplicates in original list
    duplicate_emails: List[str]
    total: int
    unique_count: int
    duplicate_count: int
    stats: Dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"Всего: {self.total} | "
            f"Уникальных: {self.unique_count} | "
            f"Дубликатов: {self.duplicate_count}"
        )


def _canonical(email: str, strip_subaddr: bool = True, collapse_aliases: bool = True) -> str:
    """Return canonical form of email for comparison."""
    email = email.strip().lower()
    if "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    # Strip sub-addressing (+tag)
    if strip_subaddr:
        local = local.split("+")[0]
        # Gmail also ignores dots in local part
        if domain in ("gmail.com", "googlemail.com"):
            local = local.replace(".", "")
    # Collapse domain aliases
    if collapse_aliases:
        domain = _DOMAIN_TO_CANONICAL.get(domain, domain)
    return f"{local}@{domain}"


def deduplicate(
    emails: Iterable[str],
    strip_subaddr: bool = True,
    collapse_aliases: bool = True,
) -> DedupResult:
    """Deduplicate a list of email addresses.

    Args:
        emails: iterable of raw email strings
        strip_subaddr: treat alice+tag@gmail.com same as alice@gmail.com
        collapse_aliases: treat googlemail.com same as gmail.com

    Returns:
        DedupResult with unique list, dupe indices, and stats.
    """
    email_list = list(emails)
    seen: Dict[str, int] = {}           # canonical → first-seen index
    unique: List[str] = []
    dupe_indices: List[int] = []
    dupe_emails: List[str] = []

    for i, raw in enumerate(email_list):
        canon = _canonical(raw, strip_subaddr, collapse_aliases)
        if canon in seen:
            dupe_indices.append(i)
            dupe_emails.append(raw)
        else:
            seen[canon] = i
            unique.append(raw)

    domain_counts = Counter(
        e.rsplit("@", 1)[1].lower() for e in unique if "@" in e
    )
    top_domains = dict(domain_counts.most_common(10))

    return DedupResult(
        unique_emails=unique,
        duplicate_indices=dupe_indices,
        duplicate_emails=dupe_emails,
        total=len(email_list),
        unique_count=len(unique),
        duplicate_count=len(dupe_indices),
        stats={"top_domains": top_domains, "alias_groups_used": int(collapse_aliases)},
    )


def find_duplicates_in_file(
    path: str,
    encoding: str = "utf-8",
    strip_subaddr: bool = True,
) -> DedupResult:
    """Convenience wrapper that reads a file (one email per line) and deduplicates."""
    from pathlib import Path
    lines = Path(path).read_text(encoding=encoding, errors="ignore").splitlines()
    emails = [l.strip() for l in lines if l.strip() and "@" in l]
    return deduplicate(emails, strip_subaddr=strip_subaddr)

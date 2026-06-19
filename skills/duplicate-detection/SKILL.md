# Duplicate Detection Skill

  ## Module: `core/duplicate_detector.py`
  Import: `from core.duplicate_detector import deduplicate, DedupResult`

  ### Functions
  | Function | Arguments | Returns |
  |---|---|---|
  | `deduplicate(emails, strip_subaddr=True, collapse_aliases=True)` | Iterable[str] | DedupResult |
  | `find_duplicates_in_file(path, encoding="utf-8")` | str | DedupResult |

  ### DedupResult attributes
  - `.unique_emails` — list, first-occurrence emails only  
  - `.duplicate_indices` — list of 0-based indices from original list  
  - `.duplicate_count` — int
  - `.summary()` — "Всего: N | Уникальных: M | Дубликатов: K"

  ### Known alias groups
  - gmail.com ↔ googlemail.com (dots/subaddr stripped)
  - hotmail.com ↔ outlook.com ↔ live.com ↔ msn.com
  - yandex.ru ↔ ya.ru ↔ yandex.com/kz/by
  - mail.ru ↔ bk.ru ↔ list.ru ↔ inbox.ru
  - protonmail.com ↔ proton.me ↔ pm.me
  - icloud.com ↔ me.com ↔ mac.com

  ### Usage in RecipientsScreen
  ```python
  from core.duplicate_detector import deduplicate
  result = deduplicate([r.email for r in self._all_recipients])
  self.dupes_label.setText(f"Дубликатов: {result.duplicate_count}")
  ```
  
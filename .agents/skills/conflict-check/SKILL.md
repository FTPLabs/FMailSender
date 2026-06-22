---
name: conflict-check
description: Проверка конфликтов между скиллами и агентами. Активируй при добавлении нового скилла/агента и при начале многоагентной сессии.
---

# Conflict Check Skill

## Карта конфликтов (известные противоречия)

### НЕТ конфликтов — совместимые скиллы

| Скилл A | Скилл B | Статус |
|---------|---------|--------|
| security-checklist | no-mock-data | ✅ Дополняют |
| repo-cleanup | size-reduction | ✅ Дополняют |
| fps-optimization | app-optimization | ✅ Дополняют |
| gui-inspector | gui-ux-principles | ✅ Дополняют |
| logging-guide | security-checklist | ✅ Дополняют |
| token-economy | agent-report | ✅ Дополняют (краткие отчёты) |
| code-review-guide | python-syntax-guard | ✅ Дополняют |

### ПОТЕНЦИАЛЬНЫЕ конфликты — правила приоритетов

| Конфликт | Правило |
|----------|---------|
| `fps-optimization` требует ограничить анимации vs `gui-ux-principles` требует feedback | Баланс: анимации ≤ 300ms, threshold 30fps для фона |
| `size-reduction` исключить модули vs `windows-exe-build` включить hidden imports | Приоритет: size-reduction (явное исключение > неявный import) |
| `repo-cleanup` удалить .pyc vs `windows-exe-build` нужны при сборке | Правило: cleanup НЕ удаляет во время сборки; после сборки ОК |
| `token-economy` (краткие отчёты) vs `agent-report` (подробные) | Приоритет: agent-report в конце задачи; token-economy в процессе |
| `no-mock-data` vs `testing-guide` (тесты нужны моки) | Граница: `tests/` папка — допустимы моки через unittest.mock |

## Проверка новых скиллов на конфликт

При добавлении нового скилла проверь:
1. Не противоречит ли MAX_CONCURRENT = 4?
2. Не нарушает ли Colors.* / Spacing.* принцип?
3. Не требует ли удалить то, что требует другой скилл оставить?
4. Не конфликтует ли с thread-safety правилами?

## Приоритеты при конфликте (убывание)

1. **secret-guard** — АБСОЛЮТНЫЙ приоритет (безопасность > всего)
2. **python-syntax-guard** — синтаксис должен работать
3. **ponytail** — минимализм
4. **security-checklist** — безопасность
5. **no-mock-data** — реальные данные
6. **gui-style-guard** — дизайн
7. Все остальные — равный приоритет

## Агенты — зоны ответственности (нет overlap)

| Агент | Файлы | НЕ трогает |
|-------|-------|-----------|
| GUI Agent | `gui/` | `core/`, `server/` |
| SMTP Expert | `core/sender.py`, `core/smtp_validator.py` | `gui/`, `server/` |
| Proxy Expert | `core/sender.py` (proxy часть) | `gui/screens/` |
| Security Agent | все файлы (read-only!) | ничего не пишет |
| DevOps | `CHANGELOG.md`, `core/_version.py`, `.github/` | `core/*.py`, `gui/` |
| Cleanup Agent | `__pycache__/`, `.pyc`, временные файлы | production `.py` |

## Синхронизация через AGENTS.md

Если агент хочет изменить правило → обновить AGENTS.md → уведомить Orchestrator.
Не молча нарушать правила других агентов.

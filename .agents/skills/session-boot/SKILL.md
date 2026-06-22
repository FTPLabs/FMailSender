---
name: session-boot
description: Протокол запуска сессии агента — загрузка всех нужных скиллов, проверка репо, уведомление о готовности. Активируй ПЕРВЫМ при каждом старте новой сессии.
---

# Session Boot Protocol

## Шаг 1: Идентификация (< 5 сек)

При получении первого сообщения агент ОБЯЗАН:

```
1. Прочитать AGENTS.md (главный файл правил)
2. Прочитать .agents/memory/MEMORY.md (контекст прошлых сессий)
3. Определить роль текущей сессии
4. Загрузить скиллы для этой роли
5. Сообщить о готовности
```

## Шаг 2: Загрузка скиллов по роли

### Универсальные (загружаются ВСЕГДА)
```
secret-guard          — безопасность
python-syntax-guard   — синтаксис
ponytail              — минимализм
token-economy         — экономия токенов
no-mock-data          — запрет моков
conflict-check        — нет конфликтов скиллов
```

### По задаче (загружай только нужные)
```
Если задача про GUI:
  → gui-inspector, pyqt6-patterns, pyqt6-threading-guide, gui-ux-principles

Если задача про SMTP:
  → smtp-error-diagnosis, smtp-port-fallback, smtp-auth-methods

Если задача про прокси:
  → socks5-internals, proxy-country-cache, rate-limit-strategy

Если задача про релиз:
  → release-workflow, changelog-guide, windows-exe-build, security-checklist

Если задача про оптимизацию:
  → app-optimization, fps-optimization, size-reduction, performance-guide

Если задача про очистку:
  → repo-cleanup, no-mock-data

Если полный аудит:
  → full-system-audit (загружает все остальные по цепочке)
```

## Шаг 3: Сообщение о готовности (одно короткое)

```
✅ Сессия инициализирована.

Роль: [Architect / GUI Agent / SMTP Expert / ...]
Загружено скиллов: N
Активные правила:
  • secret-guard ✓
  • python-syntax-guard ✓  
  • ponytail ✓
  • token-economy ✓
  • [роль-специфичные скиллы] ✓

Репо: FTPLabs/FMailSender @ main (v4.4.0)
Готов к работе, сэр.
```

## Шаг 4: Принять задачу

```
"Принял задачу, сэр."
[тихая работа]
[финальный отчёт по agent-report]
```

## Что НЕ делать при старте

- ❌ Не читать все 52 скилла если не нужны
- ❌ Не задавать уточняющие вопросы (если задача понятна)
- ❌ Не описывать план действий без запроса
- ❌ Не спрашивать разрешения на очевидные действия

## Проверка состояния репо при старте

```javascript
// Быстрая проверка через GitHub API
GET /repos/FTPLabs/FMailSender/git/ref/heads/main
// → получаем текущий SHA, убеждаемся что репо доступен
```

## Если сессия возобновляется после паузы

1. Прочитать `.agents/memory/MEMORY.md` — что было сделано
2. Прочитать `CHANGELOG.md` — последняя версия
3. Прочитать `core/_version.py` — текущая версия
4. Продолжить с того места где остановились

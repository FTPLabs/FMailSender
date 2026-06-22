---
name: full-system-audit
description: Полный аудит всех систем FMailSender перед мажорным релизом. Активируй перед MAJOR/MINOR релизами и по явному запросу "полная проверка".
---

# Full System Audit Skill

## Порядок аудита (строго последовательно)

### Фаза 1: Безопасность (security-agent)
- [ ] Нет секретов в коде (secret-guard scan)
- [ ] Пароли не логируются
- [ ] data/accounts.json в .gitignore
- [ ] Нет моковых данных (no-mock-data scan)
- [ ] SSL/TLS включён для всех SMTP подключений

### Фаза 2: Качество кода (code-reviewer)
- [ ] python -m py_compile — 0 ошибок
- [ ] flake8 --select=E9,F — нет критичных ошибок
- [ ] Нет print() в production коде
- [ ] Thread safety: все Qt вызовы из UI потока
- [ ] Все новые SmtpAccount поля с дефолтами
- [ ] .get("key", default) при чтении JSON

### Фаза 3: GUI (gui-inspector)
- [ ] Нет абсолютных координат
- [ ] Все цвета через Colors.*
- [ ] Все отступы через Spacing.*
- [ ] UI не зависает при операциях > 50ms
- [ ] FPS фоновой анимации > 25
- [ ] Скроллинг на всех больших списках

### Фаза 4: SMTP (smtp-expert)
- [ ] Все основные провайдеры в _SMTP_CONFIGS
- [ ] _parse_auth_error — понятные сообщения на русском
- [ ] PROXY_BLOCKS_SMTP только при SOCKS5 General Failure
- [ ] Таймауты заданы везде (SMTP: 15-30с)

### Фаза 5: Прокси (proxy-expert)
- [ ] _proxy_country_cache работает (v4.4.0+)
- [ ] MAX_CONCURRENT = 4
- [ ] Semaphore(3) для ip-api.com
- [ ] Воркеры очищаются после завершения

### Фаза 6: Производительность (optimizer-agent)
- [ ] Startup < 3 секунд
- [ ] EXE < 80 MB (size-reduction)
- [ ] RAM < 200 MB при 1000 аккаунтов
- [ ] Нет утечек памяти QThread

### Фаза 7: Очистка (cleanup-agent)
- [ ] Нет __pycache__ в репо
- [ ] Нет .pyc файлов
- [ ] Нет debug/test кода в production
- [ ] CHANGELOG.md обновлён
- [ ] core/_version.py обновлён

### Фаза 8: Сборка (devops-agent)
- [ ] EXE собирается без ошибок
- [ ] GitHub Actions — все workflows зелёные
- [ ] VPS деплой успешен

## Формат отчёта аудита

```
## Полный аудит v[VERSION] — [DATE]

### ✅ Пройдено
• Безопасность: 8/8 проверок OK
• Качество кода: 6/6 проверок OK
• GUI: 7/7 проверок OK
...

### ⚠️ Предупреждения
• [список незначительных проблем]

### ❌ Блокеры (релиз запрещён)
• [список критических проблем]

### Итог: [ГОТОВ К РЕЛИЗУ / ТРЕБУЕТ ИСПРАВЛЕНИЙ]
```

## Время аудита (ориентировочно)

| Фаза | Агент | Время |
|------|-------|-------|
| Безопасность | security-agent | 2-3 мин |
| Качество | code-reviewer | 3-5 мин |
| GUI | gui-inspector-agent | 2-3 мин |
| SMTP | smtp-expert | 1-2 мин |
| Прокси | proxy-expert | 1-2 мин |
| Производительность | optimizer-agent | 2-3 мин |
| Очистка | cleanup-agent | 1-2 мин |
| Сборка | devops-agent | 10-15 мин |

**Итого: ~25-35 минут на полный аудит**

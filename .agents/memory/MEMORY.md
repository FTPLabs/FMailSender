# FMailSender — Agent Memory Index

## Архитектура (v6)
- [session-boot](.agents/skills/session-boot/SKILL.md) — обязательно читать ПЕРВЫМ при каждой сессии

## Решённые нетривиальные проблемы
- asyncio.get_running_loop() — внутри корутин всегда `get_running_loop()`, не `get_event_loop()` (deprecated Python 3.10+)
- duck-compat models↔sender — models.SmtpAccount обязан иметь _lock, _day_reset, _hour_reset в __post_init__
- data/ в .gitignore — критично, иначе зашифрованные пароли попадут в репо

## Безопасность и IP-защита клиента (v6.0.6)
- Google Fonts CDN удалён из ui/index.html — слал реальный IP пользователя в Google при каждом запуске
- CSP в tauri.conf.json — connect-src ограничен 127.0.0.1:7531 и localhost:7531; внешние запросы из WebView2 заблокированы
- Системные шрифты: Segoe UI / system-ui вместо Inter (нет CDN зависимости)

## Стабильность версий (v6.0.6)
- FRONTEND_VERSION в ui/src/version.ts — сравнивается с backend /api/health.version; при несовпадении → window.location.reload() (stale WebView2 cache fix)
- release.yml обновляет ui/src/version.ts при каждом релизе (синхронно с core/_version.py)
- No-cache meta-tags в index.html предотвращают кэширование WebView2

## VPN-совместимость (v6.0.6)
- initBaseUrl() в api.ts — пробует http://127.0.0.1:7531 и http://localhost:7531; выбирает первый рабочий
- StatusContext вызывает initBaseUrl() перед первым poll — SSE URL обновляется автоматически
- main.py: FMAIL_HOST env var (дефолт 127.0.0.1); безопасно — не-loopback адреса отклоняются

## Надёжный kill процесса (v6.0.6)
- kill_existing_core() в main.rs: сначала Get-NetTCPConnection по порту 7531, затем taskkill по имени
- 1000мс sleep после kill даёт Windows освободить TCP socket и file handles
- Решает upgrade-сценарий: старый fmail-core.exe держит порт, Tauri видел OLD сервер

# FMailSender — Agent Memory Index

  ## Архитектура (v6)
  - [session-boot](.agents/skills/session-boot/SKILL.md) — обязательно читать ПЕРВЫМ при каждой сессии

  ## Решённые нетривиальные проблемы
  - asyncio.get_running_loop() — внутри корутин всегда `get_running_loop()`, не `get_event_loop()` (deprecated Python 3.10+)
  - duck-compat models↔sender — models.SmtpAccount обязан иметь _lock, _day_reset, _hour_reset в __post_init__
  - data/ в .gitignore — критично, иначе зашифрованные пароли попадут в репо
  
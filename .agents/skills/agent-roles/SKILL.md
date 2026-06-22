---
name: agent-roles
description: Описание всех специализированных агентов FMailSender — кто за что отвечает, как активировать параллельную работу. Читай ПЕРВЫМ при многоагентной задаче.
---

# Agent Roles — FMailSender Multi-Agent System

## Доступные агенты

| Агент | Файл | Специализация |
|-------|------|--------------|
| Architect | `.agents/prompts/architect.md` | Архитектурные решения, рефакторинг |
| GUI Agent | `.agents/prompts/gui-agent.md` | PyQt6 UI, дизайн, виджеты |
| SMTP Expert | `.agents/prompts/smtp-expert.md` | SMTP протокол, провайдеры |
| Proxy Expert | `.agents/prompts/proxy-expert.md` | Прокси, сетевые протоколы |
| Code Reviewer | `.agents/prompts/code-reviewer.md` | Качество кода, code review |
| Security Agent | `.agents/prompts/security-agent.md` | Безопасность, секреты |
| Tester | `.agents/prompts/tester.md` | QA, тесты, регрессии |
| DevOps | `.agents/prompts/devops-agent.md` | Сборка, CI/CD, релизы |
| Debugger | `.agents/prompts/debugger.md` | Отладка сложных проблем |
| Orchestrator | `.agents/prompts/orchestrator.md` | Координация агентов |

## Когда какой агент использовать

**Новая фича GUI** → GUI Agent + Code Reviewer
**SMTP ошибки** → SMTP Expert + Debugger (параллельно)
**Прокси проблемы** → Proxy Expert (основной) + Debugger
**Релиз** → DevOps (основной) + Security Agent + Code Reviewer
**Рефакторинг** → Architect → Code Reviewer → Tester
**Баг в production** → Debugger → SMTP/Proxy Expert (по контексту)

## Параллельная работа

Агенты могут работать параллельно если их области не пересекаются:
- GUI Agent + SMTP Expert → можно параллельно (разные файлы)
- Code Reviewer + Security Agent → можно (читают, не пишут)
- Tester + DevOps → нельзя (Tester тестирует то что DevOps собирает)

## Загрузка всех скиллов при старте

При начале новой сессии загружай скиллы по роли:
```
Architect: project-architecture, async-smtp-guide, account-persistence
GUI Agent: pyqt6-patterns, pyqt6-threading-guide, pyqt6-table-patterns, gui-ux-principles
SMTP Expert: smtp-error-diagnosis, smtp-port-fallback, smtp-auth-methods, rambler-specifics
Proxy Expert: socks5-internals, http-connect-proxy, proxy-country-cache, rate-limit-strategy
Security Agent: security-checklist
Tester: testing-guide
DevOps: windows-exe-build, release-workflow, changelog-guide
Debugger: debug-network, smtp-error-diagnosis, performance-guide
```

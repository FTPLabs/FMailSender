---
  name: agent-roles
  description: Роли агентов FMailSender — кто за что отвечает. Активируй при настройке multi-agent workflow.
  ---

  # Agent Roles — FMailSender

  ## Основные агенты

  | Агент | Файл промпта | Задача |
  |-------|-------------|-------|
  | Orchestrator | orchestrator.md | Координирует остальных агентов |
  | SMTP Expert | smtp-expert.md | Всё о SMTP, прокси, OAuth2, пуле соединений |
  | Optimizer | optimizer-agent.md | Производительность, 10к+ рассылки |
  | Debugger | debugger.md | Диагностика ошибок |
  | Security Agent | security-agent.md | Секреты, лицензия, прокси-безопасность |
  | GUI Agent | gui-agent.md | PyQt6 интерфейс |
  | DevOps Agent | devops-agent.md | Сборка, деплой, сервер |

  ## Новые модули (v5.0)

  - **core/smtp_pool.py** — пул SMTP-соединений (5-10x быстрее для 10к+)
  - **core/send_checkpoint.py** — чекпоинты кампаний (resume при крэше)

  ## Разделение ответственности

  - SMTP Expert: smtp_pool, smtp_validator, sender._send_sync
  - Optimizer: CampaignConfig оптимизация, send_checkpoint, performance-guide skill
  - GUI Agent: экраны, PyQt6, сигналы/слоты
  - Security Agent: proxy_url валидация, license.py, SECRET guard
  - DevOps: GitHub Actions, nginx, systemd service

  ## Правило для всех агентов

  Перед изменением core/sender.py → активировать скилл smtp-engine-guard.
  
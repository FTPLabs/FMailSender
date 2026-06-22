---
name: testing-guide
description: Стратегия тестирования FMailSender — unit tests, integration tests, GUI testing. Активируй при написании тестов, отладке регрессий, CI тест-конфигурации.
---

# Testing Guide

## Структура тестов

```
tests/
  test_smtp_configs.py     — тесты конфигов провайдеров
  test_proxy_parsing.py    — тесты парсинга прокси URL
  test_email_validation.py — тесты validate_email_format
  test_account_storage.py  — тесты save/load accounts
  test_message_build.py    — тесты _build_message
  test_sender_sync.py      — интеграционные тесты _test_smtp_sync
```

## Запуск

```bash
cd /path/to/fmailsender
pip install pytest
pytest tests/ -v
pytest tests/test_smtp_configs.py -v  # конкретный файл
```

## Unit тест — smtp configs

```python
# tests/test_smtp_configs.py
import pytest
from core.sender import get_smtp_config_for_domain

def test_gmail():
    cfg = get_smtp_config_for_domain("gmail.com")
    assert cfg["host"] == "smtp.gmail.com"
    assert cfg["port"] == 465
    assert cfg["use_ssl"] is True

def test_outlook():
    cfg = get_smtp_config_for_domain("outlook.com")
    assert cfg["host"] == "smtp.office365.com"
    assert cfg["port"] == 587

def test_gmx_pattern():
    cfg = get_smtp_config_for_domain("gmx.de")
    assert "gmx" in cfg["host"]

def test_unknown_domain_fallback():
    cfg = get_smtp_config_for_domain("unknowndomain12345.xyz")
    assert cfg["host"].startswith("smtp.")
```

## Unit тест — proxy parsing

```python
# tests/test_proxy_parsing.py
from core.proxy_manager import ProxyManager

def test_socks5_full():
    p = ProxyManager.parse("socks5://user:pass@1.2.3.4:1080")
    assert p == "socks5://user:pass@1.2.3.4:1080"

def test_bare_host_port():
    p = ProxyManager.parse("1.2.3.4:8080")
    assert p is not None

def test_invalid_returns_none():
    p = ProxyManager.parse("not_a_proxy")
    assert p is None
```

## GUI тестирование (без дисплея)

```python
# Используй pytest-qt для тестирования виджетов
import pytest
from PyQt6.QtWidgets import QApplication
from gui.screens.screen_accounts import AccountsScreen

@pytest.fixture
def app(qtbot):
    return QApplication.instance() or QApplication([])

def test_accounts_screen_loads(qtbot):
    screen = AccountsScreen()
    qtbot.addWidget(screen)
    assert screen.table.columnCount() == 3
```

## Интеграционный тест — SMTP (требует реальный аккаунт)

```python
# tests/test_smtp_integration.py
import os, pytest
from core.sender import SmtpAccount
from gui.screens.screen_accounts import _test_smtp_sync

@pytest.mark.skipif(not os.getenv("TEST_EMAIL"), reason="No test credentials")
def test_smtp_live():
    acc = SmtpAccount(
        email=os.getenv("TEST_EMAIL"),
        password=os.getenv("TEST_PASSWORD"),
        host="smtp.gmail.com",
        port=465,
        use_ssl=True,
        proxy=os.getenv("TEST_PROXY", "")
    )
    ok, msg = _test_smtp_sync(acc)
    assert ok, f"SMTP test failed: {msg}"
```

## CI — Python Syntax Check

Уже настроен в `.github/workflows/`:
```yaml
- name: Python Syntax Check
  run: python -m py_compile main.py core/*.py gui/**/*.py
```

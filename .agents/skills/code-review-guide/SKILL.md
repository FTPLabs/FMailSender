---
name: code-review-guide
description: Чеклист code review для FMailSender. Активируй при проверке PR, после написания крупных фич, перед релизом.
---

# Code Review Guide

## Обязательные проверки

### 1. Thread Safety
- [ ] Нет прямых вызовов Qt-методов из не-UI потоков
- [ ] Все обновления UI через сигналы/слоты или QTimer
- [ ] `QThread.quit()` вместо `terminate()` при отмене

### 2. Memory Management
- [ ] Все `QThread` хранятся в `self._workers` или `parent=self`
- [ ] Завершённые воркеры очищаются: `[w for w in list if w.isRunning()]`
- [ ] Нет циклических ссылок между виджетами и воркерами

### 3. Error Handling
- [ ] Все сетевые операции в try/except
- [ ] Таймаут задан везде (SMTP: 15-30с, HTTP API: 5-10с)
- [ ] Ошибки понятны пользователю (русский текст, без трейсбэков в UI)

### 4. Security
- [ ] Нет секретов в коде (см. `secret-guard`)
- [ ] Пароли не логируются
- [ ] Proxy credentials не в error messages

### 5. Design
- [ ] CyberPro стиль (см. `gui-style-guard`)
- [ ] `Colors.*` для всех цветов — не хардкодить
- [ ] `Spacing.*` для отступов

### 6. Code Quality (ponytail)
- [ ] Минимальный код — нет дублирования
- [ ] Новая зависимость обоснована (stdlib предпочтительна)
- [ ] Функции до ~50 строк, классы до ~300 строк

### 7. Backward Compatibility
- [ ] Новые поля SmtpAccount с дефолтами
- [ ] `.get("field", default)` при чтении JSON
- [ ] Старые форматы данных по-прежнему читаются

## Rate limits
- [ ] MAX_CONCURRENT = 4 (не менять на большее)
- [ ] ip-api.com через Semaphore(3) и кэш

## Перед merge
- [ ] `core/_version.py` обновлена
- [ ] CHANGELOG.md обновлён
- [ ] Python syntax check пройден

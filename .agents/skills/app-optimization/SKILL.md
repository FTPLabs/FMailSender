---
name: app-optimization
description: Комплексная оптимизация FMailSender — startup, SMTP throughput, память, IO. Активируй при общей просьбе "оптимизировать" и перед мажорными релизами.
---

# App Optimization Skill

## 1. Startup оптимизация (время запуска < 3 сек)

### Lazy imports
```python
# ❌ Импортируем всё при старте main.py
from core.ai_fixer import AIFixer
from core.warmup import WarmupEngine
from core.bounce import BounceParser

# ✅ Импортируем только при использовании
def _open_ai_screen(self):
    from core.ai_fixer import AIFixer  # только при открытии
    self._ai = AIFixer()
```

### Splash screen
```python
# Показать splash сразу, грузить остальное в фоне
splash = QSplashScreen(QPixmap("assets/splash.png"))
splash.show()
QApplication.processEvents()
# ... загрузка ...
splash.close()
```

### Измерение startup
```python
import time
t0 = time.monotonic()
# ... инициализация ...
print(f"Startup: {(time.monotonic()-t0)*1000:.0f}ms")
```

## 2. SMTP Throughput оптимизация

```python
# MAX_CONCURRENT = 4 — оптимум между скоростью и rate-limits
# Не увеличивай выше 4 — GMX даёт 421 при 5+

# Connection reuse (если несколько писем одному аккаунту)
# Держи smtp соединение открытым между письмами
smtp.noop()  # keepalive ping
```

## 3. IO оптимизация

### accounts.json — не перезаписывать при каждом изменении
```python
# ❌ Сохранять при каждом изменении строки
def on_account_changed(self):
    self._save_accounts()  # IO на каждый keypress

# ✅ Debounce — сохранять через 2 секунды после последнего изменения
def on_account_changed(self):
    self._save_timer.start(2000)  # QTimer, сброс при каждом вызове

def _save_debounced(self):
    self._save_accounts()  # вызывается только после паузы
```

### JSON vs SQLite для 1000+ аккаунтов
```python
# При > 1000 аккаунтов: рассмотреть SQLite (через Drizzle не нужен — это Python)
# import sqlite3 — stdlib, не нужна новая зависимость
# Но JSON достаточен до ~5000 аккаунтов при оптимизации выше
```

## 4. Сеть — пул соединений

```python
# Для ip-api.com запросов — переиспользуй TCP соединения
import urllib.request
opener = urllib.request.build_opener()
opener.addheaders = [('Connection', 'keep-alive')]
urllib.request.install_opener(opener)
```

## 5. Профилирование — найди узкое место

```python
# Запустить профайлер для конкретной операции
import cProfile, pstats, io

pr = cProfile.Profile()
pr.enable()
# ... операция ...
pr.disable()

s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
ps.print_stats(15)
print(s.getvalue())
```

## 6. Оптимизация аккаунтов — сортировка по статусу

```python
# Показывай сначала нерабочие — пользователь быстрее найдёт проблемы
accounts.sort(key=lambda a: (a.last_test_ok, a.email))
```

## Чеклист оптимизации

- [ ] Startup < 3 секунд
- [ ] Ни один UI action не блокирует > 50ms
- [ ] RAM < 200MB при 1000 аккаунтах
- [ ] SMTP валидация 100 аккаунтов < 60 сек (при хорошем прокси)
- [ ] EXE < 80 MB
- [ ] Нет утечек памяти (живые QThread = 0 после завершения)

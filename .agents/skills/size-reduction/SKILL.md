---
name: size-reduction
description: Уменьшение размера EXE и памяти FMailSender. Активируй при сборке EXE, при жалобах на большой размер, при оптимизации памяти.
---

# Size Reduction Skill

## Целевые показатели

| Метрика | Цель | Недопустимо |
|---------|------|------------|
| EXE размер | < 80 MB | > 150 MB |
| RAM при старте | < 100 MB | > 300 MB |
| RAM при работе | < 200 MB | > 500 MB |
| Время запуска | < 3 сек | > 10 сек |

## Уменьшение EXE (PyInstaller)

### UPX компрессия
```python
# В build.py — добавить UPX
subprocess.run([
    sys.executable, "-m", "PyInstaller",
    "--upx-dir", "upx/",  # папка с upx.exe
    "--upx-exclude", "vcruntime140.dll",  # некоторые DLL нельзя сжимать
    # ... остальные параметры
])
# UPX уменьшает EXE на 30-50%
```

### Исключение неиспользуемых модулей
```python
# В build.py или spec файле — явно исключай тяжёлые модули:
excludes = [
    'matplotlib',    # если не используется
    'numpy',         # если не используется
    'scipy',         # если не используется
    'pandas',        # если не используется
    'PIL.ImageTk',   # если не нужен tkinter
    'tkinter',       # не нужен (используем PyQt6)
    'unittest',      # тесты не нужны в EXE
    'pytest',        # тесты не нужны в EXE
    'doctest',
    'pdb',
]
# Добавить в PyInstaller:
# --exclude-module tkinter --exclude-module matplotlib ...
```

### Анализ что занимает место
```bash
# После сборки: анализ содержимого dist/
python -c "
import os, zipfile
total = 0
files = []
for root, dirs, fnames in os.walk('dist/_internal'):
    for f in fnames:
        p = os.path.join(root, f)
        s = os.path.getsize(p)
        total += s
        files.append((s, p))
files.sort(reverse=True)
for s, p in files[:20]:
    print(f'{s//1024:6d} KB  {p}')
print(f'Total: {total//1024//1024} MB')
"
```

## Уменьшение RAM

### QPixmap кэш
```python
# Qt кэширует QPixmap в памяти — ограничь
from PyQt6.QtWidgets import QApplication
QApplication.instance().setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

# Установи лимит кэша (в KB, default 10240 = 10MB)
from PyQt6.QtGui import QPixmapCache
QPixmapCache.setCacheLimit(5120)  # 5MB max
```

### Lazy loading изображений
```python
# ❌ Загружать все иконки при старте
self._icons = {
    "send": QIcon("assets/send.png"),
    "check": QIcon("assets/check.png"),
    # ... 50 иконок
}

# ✅ Загружать по требованию
_icon_cache: dict[str, QIcon] = {}

def get_icon(name: str) -> QIcon:
    if name not in _icon_cache:
        _icon_cache[name] = QIcon(f"assets/{name}.png")
    return _icon_cache[name]
```

### SmtpAccount — не держи лишние данные
```python
# Не держи в памяти:
# - Полный raw HTML писем
# - Бинарные данные вложений
# - Историю всех проверок (только последний результат)
@dataclass
class SmtpAccount:
    email: str
    password: str
    # ...
    last_test_ok: bool = False
    last_test_msg: str = ""  # только последнее — не список!
    # НЕ: test_history: list[...] = field(default_factory=list)
```

## requirements.txt аудит

```bash
# Проверь нужна ли каждая зависимость
pip show aiosmtplib  # используется?
pip show pillow      # используется?
pip show httpx       # используется? или заменимо на urllib?

# Замени тяжёлые библиотеки лёгкими
# requests (3MB) → httpx (2MB) → urllib (stdlib, 0MB!)
# cryptography → встроенный ssl (если достаточно)
```

## Удаление assets которые не нужны в EXE

```python
# В build.py — include ТОЛЬКО нужные assets
datas = [
    ('assets/icon.ico', 'assets'),
    ('i18n/*.qm', 'i18n'),         # скомпилированные переводы
    # НЕ включай: *.ts (исходники переводов), *.psd, *.ai
    # НЕ включай: тестовые данные
    # НЕ включай: документацию
    # НЕ включай: .git/
]
```

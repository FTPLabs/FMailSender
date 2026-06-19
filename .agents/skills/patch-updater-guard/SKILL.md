---
  name: patch-updater-guard
  description: Защищает patch-систему обновлений — make_patch.py и core/updater.py. Активируй при изменении make_patch.py, core/updater.py, main.py, или при выпуске версии с патчем.
  ---

  # Patch Updater Guard

  ## Как работает

  ```
  EXE запускается → main.py проверяет _patches/ рядом с exe
  → .py файлы там → добавляет в sys.path ПЕРВЫМ → патч переопределяет модуль
  ```

  ## Правила патча

  1. Патч — **полный** .py файл модуля, не diff
  2. Имя: `core/sender.py` → `_patches/core/sender.py`
  3. Патч совместим со ВСЕМИ версиями EXE начиная с указанной

  ## Чеклист перед выпуском патча

  ```bash
  # Синтаксис патча
  python -m py_compile _patches/core/sender.py

  # patch loader в main.py не тронут
  grep -A5 "PATCH LOADER" main.py

  # Нет новых импортов (их нет в frozen EXE!)
  grep "^import\|^from" _patches/core/sender.py
  ```

  ## Backward compatibility

  - ❌ Нельзя менять сигнатуры публичных методов
  - ❌ Нельзя добавлять новые зависимости (нет в EXE)
  - ✅ Можно исправлять логику существующих методов
  - ✅ Можно добавлять методы к существующим классам
  
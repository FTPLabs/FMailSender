---
  name: changelog-guard
  description: Поддерживает CHANGELOG.md в формате Keep a Changelog. Активируй при каждом релизе, добавлении фичи, исправлении бага, или перед созданием GitHub Release.
  ---

  # Changelog Guard — Keep a Changelog v1.1.0

  ## Формат записи

  ```markdown
  ## [3.4.2] - 2025-06-19

  ### Added
  - Новая фича (для пользователя, не для разработчика)

  ### Fixed
  - Исправлена ошибка X при условии Y

  ### Changed
  - Изменено поведение Z
  ```

  ## Правила

  1. **[Unreleased]** секция — всегда наверху, фиксации туда до релиза
  2. Версии — строго SemVer: `MAJOR.MINOR.PATCH`
  3. Даты — ISO 8601: `YYYY-MM-DD`
  4. Патч (3.4.x) — только bugfix, не новые фичи

  ## Связь с core/_version.py

  ```python
  # Единственный источник версии
  __version__ = "3.4.2"
  # При релизе: обновить _version.py И CHANGELOG.md одновременно
  ```

  ## Чеклист перед GitHub Release

  - [ ] [Unreleased] → [X.Y.Z] с датой
  - [ ] core/_version.py обновлён
  - [ ] Нет пустых секций
  - [ ] Тег соответствует: `git tag v3.4.2`
  
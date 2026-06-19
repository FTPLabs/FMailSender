---
  name: openai-guard
  description: Защищает интеграцию с OpenAI в core/ai_fixer.py. Активируй при изменении ai_fixer.py, добавлении новых AI-функций, или когда пользователь жалуется на ошибки API, высокие расходы, или зависание AI-анализа.
  ---

  # OpenAI Guard — core/ai_fixer.py

  ## Архитектура (не нарушать)

  - API ключ: **только** из `os.environ.get("OPENAI_API_KEY")` — никогда в коде
  - Запросы: **только** через `urllib.request` (stdlib) — не добавлять openai SDK
  - Всё в отдельном потоке: `threading.Thread(target=..., daemon=True)`
  - Callback-паттерн: `on_result: Callable`, `on_error: Callable`

  ## Лимиты и безопасность

  ```python
  # Обязательно ограничивать входные данные
  MAX_INPUT_CHARS = 3000  # _re_strip_html обрезает до этого

  # Обязательно timeout на запрос
  req = urllib.request.Request(...)
  urllib.request.urlopen(req, timeout=30)  # не больше 30 сек

  # Обязательно обрабатывать все ошибки
  except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
      on_error(str(e))
  ```

  ## Модели — выбор

  - `gpt-4o-mini` — по умолчанию (дёшево, быстро)
  - `gpt-4o` — только если пользователь явно выбрал в настройках
  - Никаких `gpt-4-turbo`, `gpt-3.5` — устаревшие

  ## Чеклист при добавлении новой AI-функции

  - [ ] API ключ из env, не хардкод
  - [ ] Входные данные обрезаны до разумного лимита
  - [ ] timeout установлен
  - [ ] Запуск в daemon thread, не в UI thread
  - [ ] on_error callback обрабатывает сетевые ошибки
  - [ ] Результат передаётся через сигнал PyQt6, не напрямую в виджет

  ## Экономия токенов

  ```python
  # ✅ Отправлять только текст письма, не весь HTML
  text = _re_strip_html(html_content, max_len=3000)

  # ❌ Не отправлять весь raw HTML — дорого и бесполезно
  payload = {"content": full_html}  # плохо
  ```
  
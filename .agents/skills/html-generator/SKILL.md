---
  name: html-generator
  description: Генерация HTML-шаблонов писем через AI (OpenAI / совместимый API). Активируй при запросах "сгенерируй шаблон", "создай письмо", "напиши HTML", "сделай рассылку", "уникализируй шаблон", "обойди спам через AI".
  ---

  # HTML Generator — AI Email Template Generation

  ## Архитектура (core/html_generator.py)

  ```python
  class HtmlEmailGenerator:
      """Генерирует и уникализирует HTML-шаблоны через OpenAI-совместимый API."""

      def generate_template(self, prompt: str, style: str = "professional",
                            on_result: Callable = None, on_error: Callable = None)

      def uniqueize_template(self, html: str, level: str = "medium",
                             on_result: Callable = None, on_error: Callable = None)
      # level: "light" | "medium" | "deep"
  ```

  ## Поддерживаемые AI провайдеры

  ```python
  # Настраивается в GUI → Settings → AI
  PROVIDERS = {
      "openai":    {"base_url": "https://api.openai.com/v1",           "model": "gpt-4o-mini"},
      "openrouter":{"base_url": "https://openrouter.ai/api/v1",        "model": "meta-llama/llama-3.1-8b-instruct:free"},
      "together":  {"base_url": "https://api.together.xyz/v1",         "model": "meta-llama/Llama-3-8b-chat-hf"},
      "groq":      {"base_url": "https://api.groq.com/openai/v1",      "model": "llama3-8b-8192"},
      "ollama":    {"base_url": "http://localhost:11434/v1",            "model": "llama3"},
  }
  ```

  ## Промпт для генерации шаблона

  ```
  Ты профессиональный email-маркетолог. Создай HTML-письмо по описанию.
  Требования:
  - Валидный HTML, инлайн CSS (email-клиенты не поддерживают внешний CSS)
  - Table-based layout (поддержка Outlook)
  - Alt-тексты для изображений
  - Unsubscribe ссылка в footer: {{unsubscribe_url}}
  - Мобильный адаптив (media queries)
  - Персонализация: {{first_name}}, {{company}}
  Описание: {user_prompt}
  ```

  ## Промпт для уникализации

  ```
  Перепиши это HTML-письмо чтобы:
  1. Изменить формулировки (не меняя смысл)
  2. Перефразировать заголовки и CTA
  3. Добавить невидимые вариационные символы (Zero Width Space) в слова-триггеры
  4. Изменить структуру HTML (div → table, class names)
  Уровень: {level} (light=только текст, medium=текст+структура, deep=полная переработка)
  HTML: {html_content}
  ```

  ## Интеграция в GUI (screen_compose.py)

  ```python
  # Кнопка "🤖 Генерировать" в тулбаре редактора
  self.btn_ai_generate = QPushButton("🤖 AI Шаблон")
  self.btn_ai_uniqueize = QPushButton("✨ Уникализировать")
  ```

  ## Чеклист новой AI функции

  - [ ] API ключ из env или QSettings (не хардкод)
  - [ ] Запуск в daemon thread
  - [ ] Progress indicator в GUI во время генерации
  - [ ] Результат показывается в HTML редакторе с возможностью редактировать
  - [ ] Ошибки API показываются пользователю (не тихое падение)
  
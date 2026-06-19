---
  name: spam-score-pro
  description: Умная многоуровневая проверка спам-балла письма. Активируй при изменении core/spam_checker.py, добавлении новых категорий спама, или когда пользователь говорит "письма попадают в спам", "плохой спам-балл", "улучши проверку спама", "почему спам-фильтр блокирует".
  ---

  # Spam Score Pro — Многоуровневый Анализ Спама

  ## Архитектура оценки (core/spam_checker.py)

  ```
  SpamAnalyzer.analyze(subject, body_html, sender_email)
    ├── ContentAnalyzer      → слова-триггеры, фразы, категории (0-40 pts)
    ├── StructureAnalyzer    → HTML структура, Image/Text ratio (0-20 pts)
    ├── TechnicalAnalyzer    → SPF/DKIM/DMARC, IP репутация (0-25 pts)
    ├── EngagementAnalyzer   → персонализация, ссылки, unsubscribe (0-15 pts)
    └── SpamScore(total, breakdown, recommendations)
  ```

  ## Весовые категории (data/spam_words.json)

  | Категория | Вес | Примеры |
  |-----------|-----|---------|
  | casino_gambling | 3.0 | casino, poker, jackpot |
  | money | 2.0 | free money, earn fast |
  | adult | 3.0 | explicit terms |
  | urgency | 1.5 | act now, expires today |
  | phishing | 3.0 | verify account, login required |
  | medicine | 2.5 | viagra, weight loss |
  | all_caps | 1.0 | слов написанных CAPS |
  | exclamation | 0.5 | за каждый !! |

  ## Технические проверки (новые в v3.5)

  ```python
  # 1. Соотношение изображений к тексту
  img_to_text_ratio = count_images(html) / max(len(strip_html(html)), 1)
  if img_to_text_ratio > 0.6: score += 15  # "image-only" email = spam

  # 2. Количество ссылок
  link_count = len(re.findall(r'href=', html))
  if link_count > 10: score += 10

  # 3. Скрытый текст
  if re.search(r'color:s*#fff|font-size:s*0', html): score += 20

  # 4. URL shorteners
  if re.search(r'bit.ly|tinyurl|goo.gl|t.co', html): score += 10

  # 5. Несоответствие display vs actual URL
  # <a href="http://evil.com">http://good.com</a>

  # 6. Unsubscribe ссылка (снижает балл!)
  if "unsubscribe" in html.lower() or "отписаться" in html.lower(): score -= 8
  ```

  ## Интеграция с AI (core/ai_fixer.py)

  ```python
  # Если spam_score > 60 → предлагаем AI-фикс
  if result.total_score > 60:
      ai_fixer.suggest_fix(
          subject=subject,
          body=body_html,
          spam_issues=result.breakdown,
          on_result=callback
      )
  ```

  ## Рекомендации по категориям

  ```python
  RECOMMENDATIONS = {
      "content":   "Удалите спам-слова: {words}. Используйте нейтральные синонимы.",
      "structure": "Уменьшите Image/Text ratio. Добавьте больше текста.",
      "technical": "Настройте SPF/DKIM/DMARC на домене {domain}.",
      "links":     "Сократите количество ссылок. Используйте полные URL.",
      "caps":      "Уберите текст ЗАГЛАВНЫМИ БУКВАМИ.",
  }
  ```

  ## Чеклист при расширении spam_checker.py

  - [ ] Новые слова в data/spam_words.json, не хардкод в .py
  - [ ] Вес категории обоснован (0.5-3.0)
  - [ ] Проверка работает без DNS (если dnspython недоступен)
  - [ ] Результат содержит конкретные рекомендации
  
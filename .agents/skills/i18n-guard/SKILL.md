---
  name: i18n-guard
  description: Защищает синхронизацию переводов FMailSender (Qt Linguist .ts файлы). Активируй при добавлении новых текстов в UI, изменении существующих строк, или при работе с i18n/en_US.ts и i18n/ru_RU.ts.
  ---

  # i18n Guard — Qt Linguist Translations

  ## Файлы переводов

  - `i18n/en_US.ts` — английский (основной)
  - `i18n/ru_RU.ts` — русский

  ## Правило: сначала EN, потом RU

  При добавлении новой строки UI:
  1. Добавить в `en_US.ts` с переводом
  2. Добавить туда же в `ru_RU.ts` с русским переводом
  3. Никогда не оставлять непереведённые строки (type="unfinished")

  ## Формат .ts файла

  ```xml
  <message>
      <source>Send Email</source>
      <translation>Отправить письмо</translation>
  </message>

  <!-- Незаконченный перевод — нельзя оставлять! -->
  <message>
      <source>New Feature</source>
      <translation type="unfinished"></translation>
  </message>
  ```

  ## Чеклист при добавлении текста в UI

  - [ ] Все хардкодные строки UI вынесены в .ts файлы
  - [ ] Оба файла (en + ru) обновлены
  - [ ] Нет `type="unfinished"`
  - [ ] Контекст (context name) соответствует классу PyQt6

  ## Применение в PyQt6

  ```python
  from PyQt6.QtCore import QCoreApplication
  _translate = QCoreApplication.translate

  # В коде виджета:
  self.btn.setText(_translate("ScreenCompose", "Send Email"))
  ```
  
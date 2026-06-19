---
  name: gui-status
  description: Актуальный статус GUI FMailSender: версия, расположение файлов, дизайн-токены, правила доработки.
  ---

  # GUI Status Skill — FMailSender GUI v3.6.2

  ## Текущая версия GUI

  **Активная версия:** v3.6.2 (React mockup, тёмная тема, фиолетовый акцент)  
  **Коммит:** release: GUI v3.6.2 + bugfixes v2.9.4  
  **Статус:** PRODUCTION MOCKUP — готов к портированию на PyQt6 / CustomTkinter

  ---

  ## Расположение файлов

  ```
  artifacts/mockup-sandbox/src/components/mockups/
  ├── fmail-main/
  │   ├── MainApp.tsx        ← Корневой компонент + навигация + layout
  │   ├── shared.tsx         ← Токены цветов (C), иконки (I), общие компоненты
  │   ├── TabDashboard.tsx   ← Дашборд: статы, прогресс, live-лог
  │   ├── TabAccounts.tsx    ← SMTP аккаунты: таблица, проверка
  │   ├── TabRecipients.tsx  ← Получатели: список, валидация, импорт
  │   ├── TabCompose.tsx     ← Редактор: rich text, HTML, предпросмотр, вложения
  │   ├── TabSending.tsx     ← Рассылка: настройки, прогресс, лог, контроли
  │   └── TabInbox.tsx       ← Входящие: bounce/reply/auto, ответ
  └── fmail-license/
      └── LicenseScreen.tsx  ← Экран активации лицензии

  design/
  ├── DESIGN_SYSTEM.md       ← Единый источник правды дизайна
  ├── banner.svg             ← Баннер 1200×400 (GitHub README)
  ├── avatar.svg             ← Логотип 512×512
  ├── color-palette.svg      ← Визуальная палитра 900×280
  └── icons-sprite.svg       ← SVG спрайт всех иконок

  GUI_STATUS.md              ← Этот документ (кратко)
  ```

  ---

  ## Ключевые дизайн-токены

  | Токен         | Hex / Opacity             | Назначение                        |
  |---------------|---------------------------|-----------------------------------|
  | bg            | #07090f                   | Основной фон                      |
  | surface       | #0d1117                   | Карточки, сайдбар                 |
  | surface2      | #12171f                   | Вложенные поверхности             |
  | purple        | #8b5cf6                   | Акцент, кнопки, активный nav      |
  | purpleDark    | #7c3aed                   | Hover, начало градиента           |
  | purpleLight   | #a78bfa                   | Конец градиента, светлые акценты  |
  | purpleDim     | rgba(139,92,246,0.12)     | Фон активного элемента            |
  | borderAccent  | rgba(139,92,246,0.35)     | Граница активных блоков           |
  | green         | #22c55e                   | Успех, online, валидный           |
  | red           | #ef4444                   | Ошибка, danger                    |
  | amber         | #f59e0b                   | Предупреждение, bounce            |
  | blue          | #3b82f6                   | Информация, SSL/TLS               |
  | text          | #e2e8f0                   | Основной текст                    |
  | textMuted     | rgba(255,255,255,0.38)    | Вторичный текст, лейблы           |
  | border        | rgba(255,255,255,0.07)    | Обычные границы                   |

  ---

  ## Правила доработки

  **При добавлении новой вкладки:**
  1. Создать `Tab<Name>.tsx` в `artifacts/mockup-sandbox/src/components/mockups/fmail-main/`
  2. Импортировать `C, I, Btn, Card, SectionHead` из `./shared`
  3. Зарегистрировать в `MainApp.tsx` (массив `TABS` + объект `content`)
  4. Wrapper: `padding: 22px 26px, display: flex, flexDirection: column, gap: 14, height: 100%, overflowY: auto`

  **Менять цвета** — ТОЛЬКО в `shared.tsx` (объект `C`)  
  **Добавлять иконки** — ТОЛЬКО в `shared.tsx` (объект `I`)  
  **Документация** — обновлять `design/DESIGN_SYSTEM.md` и этот файл

  ---

  ## История версий

  | Версия  | Дата       | Изменения                                              |
  |---------|------------|--------------------------------------------------------|
  | v3.6.2  | 2025-06-19 | GUI из ZIP + bugfixes v2.9.4 атомарный коммит         |
  | v3.5.5  | ранее      | Premium GUI overhaul (React mockup, тёмная тема)       |
  | <v3.0   | ранее      | Python tkinter GUI (удалён)                            |
  
# FMail Sender — GUI Status

## ✅ Новый GUI (ОСНОВНОЙ, v3.5.5)

Начиная с коммита `feat: premium GUI overhaul`, основным интерфейсом является **React-макет** (дизайн-система + mockup компоненты).

### Расположение файлов нового GUI

```
artifacts/mockup-sandbox/src/components/mockups/
├── fmail-main/           ← Главный экран (6 вкладок)
│   ├── MainApp.tsx       ← Корневой компонент
│   ├── shared.tsx        ← Токены, иконки, общие компоненты
│   ├── TabDashboard.tsx  ← Дашборд
│   ├── TabAccounts.tsx   ← SMTP аккаунты
│   ├── TabRecipients.tsx ← Получатели
│   ├── TabCompose.tsx    ← Редактор писем (rich text)
│   ├── TabSending.tsx    ← Рассылка + лог
│   └── TabInbox.tsx      ← Входящие (bounce/reply/auto)
└── fmail-license/
    └── LicenseScreen.tsx ← Экран активации лицензии

design/
├── DESIGN_SYSTEM.md      ← Полная дизайн-документация
├── banner.svg            ← Баннер 1200×400
├── avatar.svg            ← Аватар/логотип 512×512
├── color-palette.svg     ← Цветовая палитра 900×280
└── icons-sprite.svg      ← SVG спрайт всех иконок
```

### Дизайн-токены

| Токен       | Hex        |
|-------------|------------|
| bg          | #07090f    |
| surface     | #0d1117    |
| primary     | #8b5cf6    |
| success     | #22c55e    |
| error       | #ef4444    |
| warning     | #f59e0b    |

### Что было удалено

Старые Python tkinter GUI-файлы (`screen_*.py`) **удалены** из репозитория.  
Техническая часть (backend) не затронута.

### Следующий шаг

Портировать дизайн из React-макета на Python (PyQt6 / CustomTkinter / другой фреймворк).  
Все спецификации — в `design/DESIGN_SYSTEM.md`.

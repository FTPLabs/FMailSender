# FMail Sender — Design System

> Единый источник правды для дизайна FMail Sender v3.x  
> Обновлено: 2024-06-20 · Версия: 1.0.0

---

## Обзор

FMail Sender использует **тёмную тему** с акцентом на фиолетовый цвет (#8b5cf6).  
Дизайн построен на принципах: чистота, информационная плотность, профессиональный вид.

---

## Цветовая палитра

### Фоны
| Токен        | Hex        | Описание                        |
|--------------|------------|---------------------------------|
| `bg`         | `#07090f`  | Основной фон приложения         |
| `surface`    | `#0d1117`  | Карточки, сайдбар, хедер        |
| `surface2`   | `#12171f`  | Вложенные поверхности, тулбары  |

### Акцентные
| Токен          | Hex / Opacity                 | Использование                     |
|----------------|-------------------------------|-----------------------------------|
| `purple`       | `#8b5cf6`                     | Основной акцент, кнопки, активный |
| `purpleDark`   | `#7c3aed`                     | Hover, градиент от                |
| `purpleLight`  | `#a78bfa`                     | Градиент до, светлые акценты      |
| `purpleDim`    | `rgba(139,92,246,0.12)`       | Фон активного элемента            |
| `borderAccent` | `rgba(139,92,246,0.35)`       | Граница активных/акцентных блоков |

### Семантические
| Токен      | Hex        | Использование                  |
|------------|------------|-------------------------------|
| `green`    | `#22c55e`  | Успех, online, валидный         |
| `greenDim` | `rgba(34,197,94,0.10)` | Фон badge success   |
| `red`      | `#ef4444`  | Ошибка, danger, невалидный      |
| `redDim`   | `rgba(239,68,68,0.10)` | Фон badge error     |
| `amber`    | `#f59e0b`  | Предупреждение, bounce, авто    |
| `amberDim` | `rgba(245,158,11,0.10)` | Фон badge warning  |
| `blue`     | `#3b82f6`  | Информация, SSL/TLS             |
| `blueDim`  | `rgba(59,130,246,0.10)` | Фон badge info     |

### Текст
| Токен       | Значение                    | Использование               |
|-------------|-----------------------------|-----------------------------|
| `text`      | `#e2e8f0`                   | Основной текст              |
| `textMuted` | `rgba(255,255,255,0.38)`    | Вторичный, лейблы           |
| `textFaint` | `rgba(255,255,255,0.15)`    | Третичный, подсказки        |

### Утилиты
| Токен    | Значение                    | Использование        |
|----------|-----------------------------|----------------------|
| `border` | `rgba(255,255,255,0.07)`    | Обычные границы      |
| `faint`  | `rgba(255,255,255,0.06)`    | Фон inactive, hover  |

---

## Типографика

**Шрифт:** `'Inter', system-ui, -apple-system, sans-serif`  
**Моноширинный:** `monospace` (логи, email-адреса, коды, ключи)

| Размер | px  | Использование                          |
|--------|-----|----------------------------------------|
| `xs`   | 10  | Badge, лейблы колонок, meta            |
| `sm`   | 11  | Вторичный текст, timestamp в логах     |
| `base` | 13  | Основной текст приложения              |
| `md`   | 14  | Ссылки, акцентный текст                |
| `lg`   | 15–16 | Заголовки секций, топбар             |
| `xl`   | 18  | Крупные числа в карточках              |
| `2xl`  | 24–30 | Stat cards (основные цифры)          |

**Font weight:**
- `400` — обычный текст, навигация неактивная
- `500` — кнопки, лейблы
- `600` — заголовки секций, навигация активная
- `700` — stat numbers, важные данные

**Letter spacing:**
- Uppercase лейблы: `0.07–0.08em`
- Обычный текст: `-0.01em` (заголовки) или `0`

---

## Border Radius

| Значение | Использование                              |
|----------|--------------------------------------------|
| `6px`    | Маленькие элементы: badge, inline chips    |
| `8px`    | Кнопки, input поля, ячейки таблиц          |
| `10px`   | Карточки настроек, nav items              |
| `14px`   | Основные карточки, секции                 |
| `16px`   | Модальные окна                            |
| `20px`   | Попапы, license card                     |
| `99px`   | Pill badges, progress bars, индикаторы   |

---

## Тени и Свечение

```
Logo/Icon glow:  box-shadow: 0 0 18px rgba(124,58,237,0.45)
Card shadow:     box-shadow: 0 8px 40px rgba(0,0,0,0.5)
Purple glow:     box-shadow: 0 0 16px rgba(139,92,246,0.3)
Green pulse:     box-shadow: 0 0 5px #22c55e
```

---

## Компонентная система

### Кнопка (Btn)
```
Accent:  bg=#8b5cf6, border=#8b5cf6, color=#fff
Default: bg=surface, border=border, color=textMuted
Danger:  bg=redDim,  border=#ef444455, color=red
Размер:  padding 7px 14px, border-radius 8px, font-size 12px
Малый:   padding 5px 10px, font-size 11px
```

### Карточка (Card)
```
background: #0d1117
border: 1px solid rgba(255,255,255,0.07)
border-radius: 14px
```

### Таблица
```
Заголовок:   padding 10px 12px, font-size 10px, uppercase, letter-spacing 0.07em, color textMuted
Строка:      padding 9–10px 12–14px, border-bottom 1px solid border
Hover/sel:   background purpleDim (rgba(139,92,246,0.12))
Чекбокс:     15×15px, border-radius 4px, accent color=#8b5cf6
```

### Прогресс-бар
```
Track:   background rgba(255,255,255,0.06), height 4–8px, border-radius 99px
Fill:    background linear-gradient(90deg, #7c3aed, #a78bfa), transition width 0.5s ease
Micro:   height 3px (inline в таблицах)
```

### Input / Textarea
```
background: surface (#0d1117)
border: 1px solid rgba(255,255,255,0.07)
border-radius: 8px
padding: 9px 14px
font-size: 12–13px
focus: border-color rgba(139,92,246,0.6), outline none
color: #e2e8f0
caret-color: #8b5cf6
```

### Badge
```
font-size: 10px, font-weight: 600
padding: 2px 8px, border-radius: 99px
```

### Nav Item (Sidebar)
```
Размер:    padding 8px 12px, border-radius 9px, width 100%
Неакт.:   background transparent, border transparent, color textMuted
Активный: background purpleDim, border borderAccent, color purple, font-weight 600
Иконка:   15×15px SVG, currentColor
Badge:    font-size 10px, min-width 18px
```

### Модальное окно
```
Overlay:   rgba(0,0,0,0.7)
Container: background surface, border 1px solid border, border-radius 16px
padding:   28px
box-shadow: 0 8px 40px rgba(0,0,0,0.5)
```

---

## Иконки (SVG)

Все иконки — кастомные SVG, `currentColor`, размер 12–16px, stroke-width 1.2–1.4.

| Имя         | Использование               | SVG viewBox  |
|-------------|-----------------------------|--------------|
| `dashboard` | Раздел Дашборд              | 0 0 15 15    |
| `accounts`  | Раздел Аккаунты             | 0 0 15 15    |
| `recipients`| Раздел Получатели           | 0 0 15 15    |
| `compose`   | Раздел Письмо               | 0 0 15 15    |
| `sending`   | Раздел Рассылка             | 0 0 15 15    |
| `inbox`     | Раздел Входящие             | 0 0 15 15    |
| `plus`      | Добавить                    | 0 0 13 13    |
| `upload`    | Импорт / Загрузить          | 0 0 13 13    |
| `check`     | Успех / Выбор               | 0 0 12 12    |
| `x`         | Ошибка / Закрыть            | 0 0 12 12    |
| `trash`     | Удалить                     | 0 0 13 13    |
| `key`       | Лицензия                    | 0 0 14 14    |
| `settings`  | Настройки                   | 0 0 13 13    |
| `mail`      | Логотип (20×20, white)      | 0 0 20 20    |
| `bold`      | Жирный в редакторе          | 0 0 12 12    |
| `italic`    | Курсив в редакторе          | 0 0 12 12    |
| `underline` | Подчёркивание               | 0 0 12 12    |
| `link`      | Ссылка в редакторе          | 0 0 12 12    |
| `attach`    | Вложения                    | 0 0 13 13    |
| `template`  | Шаблоны                     | 0 0 13 13    |
| `spam`      | Спам-проверка               | 0 0 13 13    |
| `play`      | Запуск рассылки             | 0 0 13 13    |
| `pause`     | Пауза                       | 0 0 13 13    |
| `stop`      | Стоп                        | 0 0 13 13    |
| `clock`     | Отложенный запуск           | 0 0 13 13    |
| `reply`     | Ответить во входящих        | 0 0 13 13    |
| `filter`    | Фильтрация                  | 0 0 13 13    |
| `arrow`     | Направление / стрелка       | 0 0 12 12    |
| `download`  | Скачать / Сохранить         | 0 0 13 13    |
| `lightning` | Скорость / Молния           | 0 0 14 14    |

Полный SVG-спрайт: `design/icons-sprite.svg`  
Определения всех иконок: `artifacts/mockup-sandbox/src/components/mockups/fmail-main/shared.tsx`

---

## Анимации

```css
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.15} }   /* Live-индикаторы */
@keyframes spin   { to { transform: rotate(360deg); } }       /* Spinner */
@keyframes fadeUp { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:translateY(0)} }
@keyframes drawCheck { from{stroke-dashoffset:36} to{stroke-dashoffset:0} }
```

**Правило для счётчиков:**  
Анимировать ТОЛЬКО при монтировании (`useEffect` с пустым `[]`).  
Никогда не передавать динамически меняющееся число в аргумент — вызывает артефакты.

**Прогресс-бар:** `transition: width 0.4–0.5s ease`  
**Наведение кнопок:** `transition: all 0.12s ease`  
**Фоновые смены:** `transition: background 0.1s`

---

## Макет (Layout)

### Основное окно
```
root:    display flex, height 100vh, overflow hidden
sidebar: width 204px, flex-shrink 0
main:    flex 1, display flex, flex-direction column
```

### Sidebar
```
Header (лого):   padding 18px 14px 14px, border-bottom
Nav area:        flex 1, padding 10px 8px, gap 2px
License badge:   padding 10px 8px 14px
```

### Topbar
```
height: 52px, padding 0 24px
display: flex, align-items: center, justify-content: space-between
border-bottom: 1px solid border
```

### Tab content area
```
flex: 1, overflow: hidden, display: flex, flex-direction: column
Inner padding: 22px 26px (стандарт для всех вкладок)
gap: 14px между секциями
```

---

## Структура файлов (Mockup)

```
artifacts/mockup-sandbox/src/components/mockups/fmail-main/
├── MainApp.tsx          ← Корневой компонент, навигация, layout
├── shared.tsx           ← Токены цветов (C), иконки (I), общие компоненты
├── TabDashboard.tsx     ← Дашборд: статы, прогресс, лог
├── TabAccounts.tsx      ← SMTP аккаунты: таблица, выбор, проверка
├── TabRecipients.tsx    ← Получатели: список, валидация, импорт
├── TabCompose.tsx       ← Редактор: rich text, HTML, предпросмотр, вложения
├── TabSending.tsx       ← Рассылка: настройки, прогресс, лог, контроли
└── TabInbox.tsx         ← Входящие: bounce/reply/auto, ответ
```

---

## Экран активации лицензии

```
artifacts/mockup-sandbox/src/components/mockups/fmail-license/LicenseScreen.tsx
```

**Ключевые характеристики:**
- Минималистичный: лого + поле ключа + кнопка
- Формат ключа: `FMSND-XXXXXX-XXXXXX-XXXXXX-XXXXXX` (29 символов без авто-форматирования)
- Кнопка неактивна пока длина ключа < 29 символов
- Стадии активации: HWID → проверка → сервер → сохранение (2.6 сек)
- Экран успеха с анимированной галочкой (`drawCheck`)
- Фон: `#080b14`, карточка `rgba(255,255,255,0.03)`, `backdropFilter: blur(24px)`

---

## Assets

| Файл                     | Размер    | Описание                                   |
|--------------------------|-----------|--------------------------------------------|
| `design/banner.svg`      | 1200×400  | Официальный баннер (GitHub, README)        |
| `design/avatar.svg`      | 512×512   | Логотип / аватар приложения               |
| `design/color-palette.svg` | 900×280 | Визуальная палитра цветов                 |
| `design/icons-sprite.svg`  | —        | SVG спрайт всех иконок                    |
| `design/DESIGN_SYSTEM.md`  | —        | Этот документ (дизайн-система)            |

---

## Принципы

1. **Нет лишнего** — каждый элемент несёт функцию
2. **Информационная плотность** — максимум данных без перегруза
3. **Тёмная тема** — единственная тема, оптимизирована под длительную работу
4. **Профессиональный вид** — как инструмент, а не игрушка
5. **Кастомные SVG** — никаких emoji, никаких иконочных шрифтов
6. **CSS анимации** — предпочтительно над JS setInterval; setInterval только там где нужна настоящая динамика
7. **Monospace для данных** — email, IP, порты, коды, временны́е метки

---

## Инструкции по доработке

При добавлении новой вкладки:
1. Создать `Tab<Name>.tsx` в той же папке
2. Импортировать `C, I, Btn, Card, SectionHead` из `./shared`
3. Зарегистрировать в `MainApp.tsx` в массиве `TABS` и объекте `content`
4. Wrapper: `padding 22px 26px, display flex, flexDirection column, gap 14, height 100%, overflowY auto`

При изменении цветов — менять ТОЛЬКО в `shared.tsx` (объект `C`).  
При добавлении иконки — добавлять ТОЛЬКО в `shared.tsx` (объект `I`).

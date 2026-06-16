# GUI Style Guard Skill

## Цель
Защитить CyberPro дизайн-систему от случайного введения старых стилей.

## CyberPro Design System — правила

### Цвета (gui/theme.py — Colors)
- BG_BASE = "#040410" — основной фон (НЕЛЬЗЯ менять на #050510 или другой)
- ACCENT = "#8B5CF6" — фиолетовый неон
- CYAN = "#06B6D4" — голубой акцент
- TEXT_PRIMARY = "#E8E8FF" — основной текст
- TEXT_SECONDARY = "#6666AA" — вспомогательный текст

### Анимированный фон
- 3 орба: violet (139,92,246), cyan (6,182,212), deep violet (91,33,182)
- Aurora sweep: синусоидальный пульс opacity
- Dot grid: шаг 28px, цвет (80,80,140,18)
- Файл: gui/widgets/animated_bg.py

### Стиль карточек
- background: rgba(255,255,255,0.025)
- border: 1px solid rgba(139,92,246,0.12..0.14)
- border-radius: 12px
- НЕЛЬЗЯ: solid 1px white, border-radius > 16px, light backgrounds

### objectName aliases (используются в QSS через get_stylesheet())
- "card" — стандартная карточка
- "kpi_card" — KPI карточка с neon border
- "section_header" — заголовок секции, 18px bold
- "label_muted" — приглушённый текст #6666AA
- "label_kpi_title" — подпись KPI, uppercase 11px
- "btn_primary" — gradient violet→cyan
- "btn_secondary" — violet tint
- "btn_danger" — red tint
- "btn_icon" — ghost border

## Проверки перед коммитом

```bash
# 1. Нет старых BG цветов
grep -rn "#050510\|#0A0A1A_old\|#14142E_old" gui/ && echo "FAIL: old BG color found"

# 2. Нет hardcoded белых бордеров
grep -rn "border.*1px solid white\|border.*1px solid #fff" gui/ && echo "FAIL: white border"

# 3. get_stylesheet() должна существовать в theme.py
grep -n "def get_stylesheet" gui/theme.py || echo "FAIL: get_stylesheet missing"

# 4. AnimatedBackground должна иметь 3 орба
grep -c "_Orb(" gui/widgets/animated_bg.py | grep -q "^3$" || echo "WARN: orb count changed"
```

## При обновлении GUI
1. Всегда использовать Colors.* из gui/theme.py
2. Не менять BG_BASE, ACCENT, CYAN без согласования
3. Карточки: только rgba(255,255,255,0.02..0.04) фон
4. Новые objectName регистрировать в get_stylesheet()
5. Проверить что animated_bg.py не использует заглушки (_ORBS = [])

## Запуск тестовой проверки
```bash
python main.py --check
```
Должно вывести: "FMailSender vX.X.X — startup check OK"
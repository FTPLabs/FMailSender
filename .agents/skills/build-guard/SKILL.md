---
name: build-guard
description: Проверяет готовность проекта к сборке через Tauri v2 + PyInstaller + React/Vite. Активируй перед любым push тегом v* или workflow_dispatch в release.yml.
---

# Build Guard — FMailSender v6 (Tauri + FastAPI + React)

## Архитектура сборки

```
React (Vite) → ui/dist/
Python (PyInstaller) → src-tauri/binaries/fmail-core.exe
Tauri CLI → src-tauri/target/release/bundle/*.exe + *.msi
```

## Блок 1 — Vite base path (КРИТИЧНО для Tauri)

```bash
grep -n "base:" ui/vite.config.ts && echo "OK: base задан" || echo "FAIL: base: './' отсутствует — WebView не загрузит ресурсы"
```

**Должно быть:**
```typescript
export default defineConfig({
  base: './',   // обязательно для Tauri WebView
  ...
})
```

---

## Блок 2 — tauri-cli установлен

```bash
# В release.yml должен быть шаг:
grep -n "npm install -g @tauri-apps/cli" .github/workflows/release.yml && echo "OK" || echo "FAIL: tauri-cli не установлен в CI"
```

**Правильный вызов в CI:**
```yaml
- name: Install tauri-cli
  run: npm install -g @tauri-apps/cli@^2

- name: Generate Tauri icons
  run: tauri icon assets/images/fmail_logo.png

- name: Build Tauri
  run: tauri build
```

---

## Блок 3 — Иконки (КРИТИЧНО)

```bash
ls src-tauri/icons/ 2>/dev/null && echo "OK: icons существуют" || echo "WARN: icons сгенерируются в CI через 'tauri icon'"
```

Иконки генерируются в CI автоматически. Источник: `assets/images/fmail_logo.png`.

---

## Блок 4 — beforeBuildCommand не сломает CI

```bash
python3 -c "
import json
c = json.load(open('src-tauri/tauri.conf.json'))
cmd = c.get('build', {}).get('beforeBuildCommand', '')
if cmd and 'ui' in cmd and not cmd.startswith('cd ../ui'):
    print(f'FAIL: beforeBuildCommand={cmd!r} — путь ui/ неверен из src-tauri/')
    print('Исправление: пустая строка или cd ../ui && npm run build')
else:
    print(f'OK: beforeBuildCommand={cmd!r}')
"
```

---

## Блок 5 — Sidecar binary правильно назван

```bash
# После PyInstaller:
ls src-tauri/binaries/fmail-core-x86_64-pc-windows-msvc.exe && echo "OK" || echo "FAIL: sidecar binary не найден"
```

Tauri ищет: `binaries/fmail-core-x86_64-pc-windows-msvc.exe` (суффикс цели Rust).

---

## Блок 6 — PyInstaller spec (PyInstaller >= 6.0)

```bash
grep -n "^cipher\|PYZ.*cipher=" fmail-core.spec && echo "FAIL: устаревший cipher= в PYZ()" || echo "OK: PyInstaller 6.x (комментарии с 'cipher=' не считаются)"
grep -n "upx=True" fmail-core.spec && echo "WARN: UPX может не быть в CI — используй upx=False" || echo "OK: upx=False"
```

---

## Блок 7 — aiosmtplib >= 3.0

```bash
grep -rn "start_tls=" core/sender.py && echo "FAIL: start_tls= убран в aiosmtplib 3.0" || echo "OK"
```

**Правильный паттерн:**
```python
# SSL (порт 465):
smtp = aiosmtplib.SMTP(hostname=host, port=465, use_tls=True, timeout=30)
await smtp.connect()
# STARTTLS (порт 587):
smtp = aiosmtplib.SMTP(hostname=host, port=587, use_tls=False, timeout=30)
await smtp.connect()
await smtp.starttls()
```

---

## Блок 8 — Tag name при workflow_dispatch

```bash
grep -n "steps.tag.outputs.tag" .github/workflows/release.yml && echo "OK: tag формируется правильно" || echo "FAIL: tag_name возьмёт имя ветки вместо версии"
```

**Правильно:**
```yaml
- name: Determine release tag
  id: tag
  shell: bash
  run: |
    if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
      echo "tag=v${{ github.event.inputs.version }}" >> $GITHUB_OUTPUT
    else
      echo "tag=${{ github.ref_name }}" >> $GITHUB_OUTPUT
    fi
```

---

## Полный pre-build чеклист

```bash
echo "=== Build Guard v6.0 (Tauri) ==="

# 1. Vite base
grep -q "base:" ui/vite.config.ts && echo "1. Vite base OK" || echo "1. FAIL: base: './' отсутствует"

# 2. tauri-cli в CI
grep -q "@tauri-apps/cli" .github/workflows/release.yml && echo "2. tauri-cli OK" || echo "2. FAIL: tauri-cli не установлен"

# 3. beforeBuildCommand
python3 -c "
import json; c = json.load(open('src-tauri/tauri.conf.json'))
cmd = c['build'].get('beforeBuildCommand','')
print('3. beforeBuildCommand OK' if not (cmd and 'cd ui' in cmd and not '../ui' in cmd) else '3. FAIL: неверный путь')
"

# 4. PyInstaller 6.x
! grep -q "cipher=block_cipher" fmail-core.spec && echo "4. PyInstaller 6.x OK" || echo "4. FAIL: cipher="

# 5. UPX
! grep -q "upx=True" fmail-core.spec && echo "5. UPX OK (False)" || echo "5. WARN: upx=True может упасть"

# 6. aiosmtplib
! grep -rq "start_tls=" core/sender.py && echo "6. aiosmtplib OK" || echo "6. FAIL: start_tls="

# 7. Python синтаксис
python3 -m py_compile main.py core/server.py core/sender.py && echo "7. Python syntax OK" || echo "7. SYNTAX ERROR"

# 8. Tag name
grep -q "steps.tag.outputs" .github/workflows/release.yml && echo "8. Tag name OK" || echo "8. FAIL: tag_name неверен"

echo "=== Done ==="
```

---

## Триггер сборки

```bash
# По тегу:
git tag v6.0.1
git push origin v6.0.1

# Вручную через GitHub Actions:
# Actions → Build & Release → Run workflow → Version: 6.0.1
```

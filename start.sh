#!/usr/bin/env bash
# FMailSender — автозапуск в браузере
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Проверка Node.js ──────────────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
  echo ""
  echo " [!] Node.js не найден."
  echo "     Установите: https://nodejs.org (LTS)"
  echo "     Ubuntu/Debian: sudo apt install nodejs npm"
  echo ""
  exit 1
fi

mkdir -p logs

# ── Первый запуск: зависимости ───────────────────────────────────────────────
if [ ! -d "backend/node_modules" ]; then
  echo " [1/3] Первый запуск — зависимости backend..."
  cd backend && npm install --prefer-offline --loglevel=error 2>&1 | tail -3; cd ..
fi

if [ ! -d "ui/node_modules" ]; then
  echo " [2/3] Первый запуск — зависимости UI..."
  cd ui && npm install --prefer-offline --loglevel=error 2>&1 | tail -3; cd ..
fi

if [ ! -f "ui/dist/index.html" ]; then
  echo " [3/3] Первый запуск — сборка интерфейса (~15 сек)..."
  cd ui && npm run build 2>&1 | tail -6; cd ..
fi

# ── Запуск backend ────────────────────────────────────────────────────────────
echo ""
echo " Запуск FMailSender..."
FMAIL_PORT=7531 node backend/src/server.js >logs/backend.log 2>&1 &
BACKEND_PID=$!

# ── Ожидание готовности ───────────────────────────────────────────────────────
attempt=0
until curl -sf http://127.0.0.1:7531/api/health &>/dev/null; do
  attempt=$((attempt + 1))
  if [ $attempt -gt 30 ]; then break; fi
  sleep 1
done

# ── Открыть браузер ───────────────────────────────────────────────────────────
URL="http://localhost:7531"
if command -v xdg-open &>/dev/null; then
  xdg-open "$URL" &>/dev/null &
elif command -v open &>/dev/null; then
  open "$URL" &>/dev/null &
else
  echo " Откройте браузер вручную: $URL"
fi

echo ""
echo " ┌─────────────────────────────────────────────┐"
echo " │  FMailSender запущен: $URL   │"
echo " │  Ctrl+C — остановить приложение             │"
echo " └─────────────────────────────────────────────┘"
echo ""

# ── Держим процесс до Ctrl+C ──────────────────────────────────────────────────
trap "echo ''; echo ' Остановка...'; kill $BACKEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM
wait $BACKEND_PID

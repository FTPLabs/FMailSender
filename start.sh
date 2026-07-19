#!/usr/bin/env bash
# FMailSender — запуск в браузере (без Electron)
# Требования: Node.js 18+
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Установка зависимостей backend
if [ ! -d "backend/node_modules" ]; then
  echo "📦 Устанавливаю зависимости backend..."
  cd backend && npm install --prefer-offline 2>&1 | tail -3; cd ..
fi

# Сборка UI если нет dist/
if [ ! -f "ui/dist/index.html" ]; then
  echo "🔨 Собираю UI..."
  cd ui
  if [ ! -d "node_modules" ]; then npm install --prefer-offline 2>&1 | tail -3; fi
  npm run build
  cd ..
fi

echo ""
echo "🚀 Запускаю FMailSender на http://localhost:7531"
echo "   Откройте браузер: http://localhost:7531"
echo "   Ctrl+C — остановить"
echo ""

FMAIL_PORT=7531 node backend/src/server.js

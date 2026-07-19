@echo off
:: FMailSender — запуск в браузере (без Electron)
:: Требования: Node.js 18+
cd /d "%~dp0"

if not exist "backend\node_modules" (
    echo [*] Устанавливаю зависимости backend...
    cd backend && npm install --prefer-offline && cd ..
)

if not exist "ui\dist\index.html" (
    echo [*] Собираю UI...
    cd ui
    if not exist "node_modules" npm install --prefer-offline
    npm run build
    cd ..
)

echo.
echo [*] Запускаю FMailSender на http://localhost:7531
echo     Откройте браузер: http://localhost:7531
echo     Ctrl+C - остановить
echo.

set FMAIL_PORT=7531
node backend\src\server.js

@echo off
chcp 65001 >nul 2>&1
title FMailSender
cd /d "%~dp0"

:: ── Проверка Node.js ──────────────────────────────────────────────────────────
where node >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [!] Node.js не найден.
    echo      Скачайте и установите: https://nodejs.org  ^(LTS^)
    echo      После установки запустите start.bat снова.
    echo.
    pause
    exit /b 1
)

:: ── Создать папку логов ───────────────────────────────────────────────────────
if not exist "logs" mkdir logs

:: ── Первый запуск: установка зависимостей ────────────────────────────────────
if not exist "backend\node_modules" (
    echo  [1/3] Первый запуск — установка зависимостей backend...
    cd backend
    npm install --prefer-offline --loglevel=error 2>nul
    if errorlevel 1 ( npm install --loglevel=error )
    cd ..
)

if not exist "ui\node_modules" (
    echo  [2/3] Первый запуск — установка зависимостей UI...
    cd ui
    npm install --prefer-offline --loglevel=error 2>nul
    if errorlevel 1 ( npm install --loglevel=error )
    cd ..
)

if not exist "ui\dist\index.html" (
    echo  [3/3] Первый запуск — сборка интерфейса ^(~15 сек^)...
    cd ui
    npm run build 2>&1 | findstr /v "^$"
    if errorlevel 1 (
        echo  [!] Ошибка сборки интерфейса. Подробности: ui\build.log
        pause
        exit /b 1
    )
    cd ..
)

:: ── Запуск backend в фоне ────────────────────────────────────────────────────
echo.
echo  Запуск FMailSender...
set FMAIL_PORT=7531
start /b "" node backend\src\server.js >logs\backend.log 2>&1

:: ── Ожидание готовности (polling /api/health) ─────────────────────────────────
set /a attempt=0
:poll
set /a attempt+=1
if %attempt% gtr 30 goto open_browser
timeout /t 1 /nobreak >nul
curl -s -f -o nul http://127.0.0.1:7531/api/health 2>nul
if errorlevel 1 goto poll

:open_browser
:: ── Открыть браузер ──────────────────────────────────────────────────────────
start "" http://localhost:7531

echo.
echo  ┌─────────────────────────────────────────────┐
echo  │  FMailSender запущен                        │
echo  │  Адрес: http://localhost:7531               │
echo  │                                             │
echo  │  Не закрывайте это окно — оно держит        │
echo  │  приложение запущенным.                     │
echo  │  Для выхода: Ctrl+C или закройте окно.      │
echo  └─────────────────────────────────────────────┘
echo.

:: Ждём пока node завершится (держим окно открытым)
:keepalive
timeout /t 5 /nobreak >nul
curl -s -f -o nul http://127.0.0.1:7531/api/health 2>nul
if not errorlevel 1 goto keepalive

echo.
echo  FMailSender остановлен.
pause

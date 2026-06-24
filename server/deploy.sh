#!/bin/bash
# ============================================================
# FMailSender VPS — Deploy / Update Script v3.0.0
# Запуск: bash /opt/fmailsender/server/deploy.sh
# ============================================================
set -e

APP_DIR="/opt/fmailsender"
SERVICE="fmailsender"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === FMailSender Deploy Start ==="

cd "${APP_DIR}"
git fetch origin
git reset --hard origin/main
echo "✅ Код: $(git log --oneline -1)"

VENV="${APP_DIR}/venv"
if [ ! -f "${VENV}/bin/pip" ]; then
    echo "⚙️  Создаём venv..."
    python3 -m venv "${VENV}"
fi
"${VENV}/bin/pip" install -q --upgrade pip
"${VENV}/bin/pip" install -q -r "${APP_DIR}/server/requirements.txt"
echo "✅ Зависимости обновлены"

# Обновляем systemd unit если изменился
if ! diff -q "${APP_DIR}/server/fmailsender.service" /etc/systemd/system/fmailsender.service > /dev/null 2>&1; then
    echo "⚙️  Обновляем systemd unit..."
    cp "${APP_DIR}/server/fmailsender.service" /etc/systemd/system/fmailsender.service
fi

# Обновляем watchdog
if [ -f "${APP_DIR}/server/watchdog.sh" ]; then
    chmod +x "${APP_DIR}/server/watchdog.sh"
    cp "${APP_DIR}/server/watchdog.sh" /opt/fmailsender/server/watchdog.sh 2>/dev/null || true
fi

systemctl daemon-reload
systemctl restart "${SERVICE}"
sleep 5

STATUS=$(systemctl is-active "${SERVICE}" 2>/dev/null || echo "unknown")
if [ "${STATUS}" = "active" ]; then
    echo "✅ Сервис ${SERVICE}: ACTIVE"
else
    echo "❌ Сервис не запустился (status=${STATUS})"
    journalctl -u "${SERVICE}" -n 40 --no-pager
    exit 1
fi

# Проверяем nginx
NGINX_STATUS=$(systemctl is-active nginx 2>/dev/null || echo "unknown")
if [ "${NGINX_STATUS}" != "active" ]; then
    echo "⚠️  Nginx не запущен — перезапуск..."
    systemctl start nginx
else
    echo "✅ Nginx: ACTIVE"
fi

# Убеждаемся, что watchdog cron на месте
if [ ! -f /etc/cron.d/fmailsender-watchdog ]; then
    echo "⚙️  Устанавливаем watchdog cron..."
    bash "${APP_DIR}/server/watchdog.sh" --install
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === Deploy complete ==="

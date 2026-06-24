#!/bin/bash
# ============================================================
# FMailSender Watchdog
# Проверяет и поднимает все сервисы если они упали.
# Запускается каждую минуту через cron.
# Установка: bash /opt/fmailsender/server/watchdog.sh --install
# ============================================================

LOG="/var/log/fmailsender-watchdog.log"
MAX_LOG_LINES=1000

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"
}

trim_log() {
    if [ -f "$LOG" ]; then
        local lines
        lines=$(wc -l < "$LOG" 2>/dev/null || echo 0)
        if [ "$lines" -gt "$MAX_LOG_LINES" ]; then
            tail -n 500 "$LOG" > "${LOG}.tmp" && mv "${LOG}.tmp" "$LOG"
        fi
    fi
}

check_and_restart() {
    local SERVICE="$1"
    local STATUS
    STATUS=$(systemctl is-active "$SERVICE" 2>/dev/null || echo "unknown")
    if [ "$STATUS" != "active" ]; then
        log "⚠️  $SERVICE is $STATUS — restarting..."
        systemctl start "$SERVICE" 2>>"$LOG"
        sleep 3
        STATUS=$(systemctl is-active "$SERVICE" 2>/dev/null || echo "unknown")
        if [ "$STATUS" = "active" ]; then
            log "✅ $SERVICE restarted successfully"
        else
            log "❌ $SERVICE FAILED to start (status=$STATUS)"
            # Попробуем daemon-reload и ещё раз
            systemctl daemon-reload 2>/dev/null
            systemctl start "$SERVICE" 2>>"$LOG"
        fi
    fi
}

install_cron() {
    SCRIPT_PATH="/opt/fmailsender/server/watchdog.sh"
    CRON_LINE="* * * * * root bash $SCRIPT_PATH >> /var/log/fmailsender-watchdog.log 2>&1"
    CRON_FILE="/etc/cron.d/fmailsender-watchdog"

    cp "$0" "$SCRIPT_PATH" 2>/dev/null || true
    chmod +x "$SCRIPT_PATH"

    if [ ! -f "$CRON_FILE" ] || ! grep -q "fmailsender" "$CRON_FILE" 2>/dev/null; then
        echo "$CRON_LINE" > "$CRON_FILE"
        chmod 644 "$CRON_FILE"
        echo "✅ Watchdog cron установлен: $CRON_FILE"
    else
        echo "✅ Watchdog cron уже установлен"
    fi

    # Убеждаемся что cron сам включён
    systemctl enable cron 2>/dev/null || systemctl enable crond 2>/dev/null || true
    systemctl start cron 2>/dev/null || systemctl start crond 2>/dev/null || true
}

# ── Режим установки ─────────────────────────────────────────
if [ "$1" = "--install" ]; then
    install_cron
    exit 0
fi

# ── Основная проверка ────────────────────────────────────────
trim_log

# 1. Бот + API сервер
check_and_restart "fmailsender"

# 2. Nginx (сайт / reverse proxy)
check_and_restart "nginx"

# 3. Обновление SSL сертификата (раз в сутки, certbot сам решает нужно ли)
if [ "$(date +%H:%M)" = "04:30" ]; then
    certbot renew --quiet --deploy-hook "systemctl reload nginx" >> "$LOG" 2>&1 && \
        log "🔒 Certbot renew: OK"
fi

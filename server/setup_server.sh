#!/bin/bash
# ============================================================
# FMailSender VPS Full Setup Script v3.0.0
# Бот + FastAPI + Nginx + SSL + Watchdog + Автоперезапуск
# ============================================================
set -e

APP_DIR="/opt/fmailsender"
DOMAIN="fmail.shop"
EMAIL="admin@fmail.shop"

echo "=== [1/9] Обновление системы ==="
apt-get update -y
apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git curl ufw cron

echo "=== [2/9] Настройка файрвола ==="
ufw allow 22
ufw allow 80
ufw allow 443
ufw --force enable

echo "=== [3/9] Клонирование / обновление репозитория ==="
if [ -d "$APP_DIR/.git" ]; then
    cd "$APP_DIR"
    git fetch origin
    git reset --hard origin/main
    echo "✅ Обновлено: $(git log --oneline -1)"
else
    if [ -z "$GH_TOKEN" ]; then
        echo "ERROR: GH_TOKEN не задан. export GH_TOKEN=your_token"
        exit 1
    fi
    git clone "https://${GH_TOKEN}@github.com/FTPLabs/FMailSender.git" "$APP_DIR"
    cd "$APP_DIR"
fi

echo "=== [4/9] Python venv и зависимости ==="
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/server/requirements.txt"

echo "=== [5/9] Настройка .env ==="
if [ ! -f "$APP_DIR/server/.env" ]; then
    cat > "$APP_DIR/server/.env" << 'EOF'
# ⚠️  ЗАПОЛНИ ВСЕ ЗНАЧЕНИЯ ДО ЗАПУСКА!
BOT_TOKEN=
ADMIN_IDS=
CRYPTO_BOT_TOKEN=
HWID_SALT=
JWT_SECRET=
DB_PATH=/opt/fmailsender/server/fmailsender.db
API_HOST=127.0.0.1
API_PORT=8000
NO_SSL=1
EOF
    chmod 600 "$APP_DIR/server/.env"
    echo "⚠️  Создан $APP_DIR/server/.env — ОБЯЗАТЕЛЬНО заполни перед запуском!"
fi

echo "=== [6/9] Nginx ==="
cp "$APP_DIR/server/nginx.conf" "/etc/nginx/sites-available/$DOMAIN"
ln -sf "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/$DOMAIN"
rm -f /etc/nginx/sites-enabled/default
mkdir -p /var/www/certbot
nginx -t
# Включаем nginx в автозапуск
systemctl enable nginx
systemctl start nginx || systemctl reload nginx
echo "✅ Nginx запущен и включён в автозапуск"

echo "=== [7/9] SSL сертификат (Let's Encrypt) ==="
echo "Убедись, что DNS для $DOMAIN указывает на этот сервер!"
read -p "DNS настроен? Продолжить? [y/N] " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
    certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" \
        --non-interactive --agree-tos --email "$EMAIL" \
        --redirect
    systemctl reload nginx
    echo "✅ SSL получен"
else
    echo "⏭️  SSL пропущен. Запусти вручную: certbot --nginx -d $DOMAIN"
fi

echo "=== [8/9] Systemd сервис (бот + API) ==="
cp "$APP_DIR/server/fmailsender.service" /etc/systemd/system/fmailsender.service
systemctl daemon-reload
systemctl enable fmailsender
systemctl restart fmailsender
sleep 3
STATUS=$(systemctl is-active fmailsender 2>/dev/null || echo "unknown")
if [ "$STATUS" = "active" ]; then
    echo "✅ fmailsender: ACTIVE"
else
    echo "❌ fmailsender не запустился (status=$STATUS)"
    journalctl -u fmailsender -n 30 --no-pager
fi

echo "=== [9/9] Watchdog (автоподнятие каждую минуту через cron) ==="
chmod +x "$APP_DIR/server/watchdog.sh"
bash "$APP_DIR/server/watchdog.sh" --install

echo ""
echo "============================================="
echo "✅ FMailSender установлен!"
echo ""
echo "Статус бота:  systemctl status fmailsender"
echo "Логи бота:    journalctl -u fmailsender -f"
echo "Watchdog лог: tail -f /var/log/fmailsender-watchdog.log"
echo "Nginx:        systemctl status nginx"
echo "Домен:        https://$DOMAIN"
echo "============================================="
echo ""
echo "Автоподнятие настроено:"
echo "  • systemd: Restart=always, StartLimitIntervalSec=0"
echo "  • cron watchdog: каждую минуту проверяет бот и nginx"
echo "  • nginx: включён в автозапуск (systemctl enable nginx)"
echo ""
echo "Обновление в будущем: bash $APP_DIR/server/deploy.sh"

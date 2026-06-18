#!/bin/bash
# ============================================================
# FMailSender VPS Setup Script
# Сервер: YOUR_SERVER_IP
# Домен: fmail.shop
# SSL: Let's Encrypt
# ============================================================
set -e

APP_DIR="/opt/fmailsender"
DOMAIN="fmail.shop"
EMAIL="admin@fmail.shop"

echo "=== [1/8] Обновление системы ==="
apt-get update -y
apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git curl ufw

echo "=== [2/8] Настройка файрвола ==="
ufw allow 22
ufw allow 80
ufw allow 443
# ufw allow 8000  # FastAPI НЕ открываем наружу — только через nginx
ufw --force enable

echo "=== [3/8] Копирование файлов приложения ==="
mkdir -p "$APP_DIR"
# Копируем из текущей директории (запускаем из корня репозитория)
cp -r . "$APP_DIR/"

echo "=== [4/8] Создание Python виртуального окружения ==="
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/server/requirements.txt"

echo "=== [5/8] Настройка .env (если не существует) ==="
if [ ! -f "$APP_DIR/server/.env" ]; then
    cat > "$APP_DIR/server/.env" << 'EOF'
# Заполни эти значения!
BOT_TOKEN=
ADMIN_IDS=
JWT_SECRET=
DATABASE_PATH=fmailsender.db
API_HOST=127.0.0.1
API_PORT=8000
NO_SSL=1
EOF
    echo "⚠️  Создан $APP_DIR/server/.env — ОБЯЗАТЕЛЬНО заполни значения!"
fi

echo "=== [6/8] Настройка Nginx ==="
cp "$APP_DIR/server/nginx.conf" "/etc/nginx/sites-available/$DOMAIN"
ln -sf "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/$DOMAIN"
rm -f /etc/nginx/sites-enabled/default
mkdir -p /var/www/certbot
nginx -t
systemctl reload nginx

echo "=== [7/8] Получение SSL сертификата (Let's Encrypt) ==="
echo "Убедись, что DNS для $DOMAIN уже указывает на этот сервер!"
read -p "DNS настроен? Продолжить получение SSL? [y/N] " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
    certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" \
        --non-interactive --agree-tos --email "$EMAIL" \
        --redirect
    systemctl reload nginx
    echo "✅ SSL сертификат получен"
else
    echo "⏭️  SSL пропущен. Запусти вручную: certbot --nginx -d $DOMAIN -d www.$DOMAIN"
fi

echo "=== [8/8] Настройка systemd сервиса ==="
sed "s|/opt/fmailsender|$APP_DIR|g" "$APP_DIR/server/fmailsender.service" > /etc/systemd/system/fmailsender.service
systemctl daemon-reload
systemctl enable fmailsender
systemctl restart fmailsender

echo ""
echo "============================================="
echo "✅ FMailSender успешно установлен!"
echo "📊 Статус: systemctl status fmailsender"
echo "📋 Логи:   journalctl -u fmailsender -f"
echo "🌐 Домен:  https://$DOMAIN"
echo "============================================="
echo ""
echo "Инструкция по Cloudflare:"
echo "1. Добавь домен $DOMAIN в Cloudflare"
echo "2. DNS → A запись: $DOMAIN → $(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_SERVER_IP') (Proxied ✅)"
echo "3. SSL/TLS → Full (strict)"
echo "4. SSL/TLS → Edge Certificates → Always Use HTTPS → ON"

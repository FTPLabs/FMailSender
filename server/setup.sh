#!/bin/bash
# FMail Sender — VPS Setup & Deploy Script v3.0.0
set -e

echo "=== FMail Sender Bot Setup v3.0.0 ==="

apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl cron

cd /opt
if [ -d "fmailsender" ]; then
    echo "Updating existing installation..."
    cd fmailsender
    git fetch origin
    git reset --hard origin/main
else
    echo "Cloning repository..."
    if [ -z "$GH_TOKEN" ]; then
        echo "ERROR: GH_TOKEN env var is required to clone private repo."
        echo "Export it: export GH_TOKEN=your_github_token"
        exit 1
    fi
    git clone "https://${GH_TOKEN}@github.com/FTPLabs/FMailSender.git" fmailsender
    cd fmailsender
fi

cd server
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ ! -f /opt/fmailsender/server/.env ]; then
    cat > /opt/fmailsender/server/.env << 'ENVEOF'
BOT_TOKEN=REPLACE_WITH_BOT_TOKEN
ADMIN_IDS=REPLACE_WITH_ADMIN_TELEGRAM_ID
CRYPTO_BOT_TOKEN=REPLACE_WITH_CRYPTO_BOT_TOKEN
HWID_SALT=REPLACE_WITH_RANDOM_SALT_STRING
JWT_SECRET=REPLACE_WITH_MIN_32_CHAR_SECRET
DB_PATH=/opt/fmailsender/server/licenses.db
API_HOST=0.0.0.0
API_PORT=8000
ENVEOF
    chmod 600 /opt/fmailsender/server/.env
    echo ".env created — FILL IT IN before starting!"
else
    echo ".env already exists, skipping"
fi

# ── Systemd сервис ───────────────────────────────────────────
cp /opt/fmailsender/server/fmailsender.service /etc/systemd/system/fmailsender.service

systemctl daemon-reload
systemctl enable fmailsender
systemctl restart fmailsender

# ── Watchdog (автоподнятие через cron) ──────────────────────
chmod +x /opt/fmailsender/server/watchdog.sh
bash /opt/fmailsender/server/watchdog.sh --install

echo ""
echo "=== Setup complete! ==="
systemctl status fmailsender --no-pager -l
echo ""
echo "Logs:    journalctl -u fmailsender -f"
echo "Watchdog log: tail -f /var/log/fmailsender-watchdog.log"

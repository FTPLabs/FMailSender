#!/bin/bash
# FMail Sender — VPS Setup & Deploy Script v2.5.0
set -e

echo "=== FMail Sender Bot Setup v2.5.0 ==="

apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl

cd /opt
if [ -d "fmailsender" ]; then
    echo "Updating existing installation..."
    cd fmailsender
    git fetch origin
    git reset --hard origin/main
else
    echo "Cloning repository..."
    git clone https://github.com/FTPLabs/FMailSender.git fmailsender
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
    echo ".env created"
else
    echo ".env already exists, skipping"
fi

printf "[Unit]\nDescription=FMail Sender Telegram Bot + License API\nAfter=network.target\nWants=network-online.target\n\n[Service]\nType=simple\nUser=root\nWorkingDirectory=/opt/fmailsender/server\nEnvironmentFile=/opt/fmailsender/server/.env\nExecStart=/opt/fmailsender/server/venv/bin/python bot.py\nRestart=always\nRestartSec=5\nStandardOutput=journal\nStandardError=journal\nSyslogIdentifier=fmailsender\n\n[Install]\nWantedBy=multi-user.target\n" > /etc/systemd/system/fmailsender.service

systemctl daemon-reload
systemctl enable fmailsender
systemctl restart fmailsender

echo "=== Setup complete! ==="
systemctl status fmailsender --no-pager

#!/bin/bash
# FMail Sender — VPS Setup Script
set -e

echo "=== FMail Sender Bot Setup ==="

apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git

cd /opt
if [ -d "fmailsender" ]; then
    cd fmailsender
    git pull origin main
else
    git clone https://github.com/FTPLabs/EmailSenderPro.git fmailsender
    cd fmailsender
fi

cd server
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

cat > .env << 'ENVEOF'
BOT_TOKEN=8869596289:AAFN22KeV6yp8oVCWwDTxu34wEc7Z-HX4bI
ADMIN_IDS=8784635852
CRYPTO_BOT_TOKEN=594916:AA6n54rTVfzrbCljPW33D49EVwHyDEpmW6f
HWID_SALT=FMSND-PRODUCTION-SALT-X9K2-7B4Q-3F8W-1T5R
JWT_SECRET=fmsnd-jwt-2026-X9K2M7B4Q3F8W1T5R6Y9P0
DB_PATH=/opt/fmailsender/server/licenses.db
API_HOST=0.0.0.0
API_PORT=8000
ENVEOF

cat > /etc/systemd/system/fmailsender-bot.service << 'SERVICEEOF'
[Unit]
Description=FMail Sender Bot + License API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/fmailsender/server
EnvironmentFile=/opt/fmailsender/server/.env
ExecStart=/opt/fmailsender/server/venv/bin/python bot.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable fmailsender-bot
systemctl restart fmailsender-bot

echo ""
echo "=== Setup Complete ==="
echo "Status: $(systemctl is-active fmailsender-bot)"
echo "API:    http://31.76.100.190:8000/health"
echo ""
echo "Logs: journalctl -u fmailsender-bot -f"

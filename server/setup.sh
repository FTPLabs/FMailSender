#!/bin/bash
# FMail Sender — VPS Setup & Deploy Script
set -e

echo "=== FMail Sender Bot Setup ==="

# Install system dependencies
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl

# Clone or update repo
cd /opt
if [ -d "fmailsender" ]; then
    echo "Updating existing installation..."
    cd fmailsender
    git fetch origin
    git reset --hard origin/main
else
    echo "Cloning repository..."
    git clone https://github.com/FTPLabs/EmailSenderPro.git fmailsender
    cd fmailsender
fi

# Setup Python venv and install dependencies
cd server
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# Write .env file
cat > /opt/fmailsender/server/.env << 'ENVEOF'
BOT_TOKEN=8869596289:AAFN22KeV6yp8oVCWwDTxu34wEc7Z-HX4bI
ADMIN_IDS=8784635852
CRYPTO_BOT_TOKEN=594916:AA6n54rTVfzrbCljPW33D49EVwHyDEpmW6f
HWID_SALT=FMSND-PRODUCTION-SALT-X9K2-2026
JWT_SECRET=fmsnd-jwt-2026-X9K2M7B4Q3F8W1T5R6Y9P0
DB_PATH=/opt/fmailsender/server/licenses.db
API_HOST=0.0.0.0
API_PORT=8000
ENVEOF

chmod 600 /opt/fmailsender/server/.env

# Create systemd service
cat > /etc/systemd/system/fmailsender.service << 'SERVICEEOF'
[Unit]
Description=FMail Sender — Telegram Bot + License API
After=network.target
Wants=network-online.target

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
SyslogIdentifier=fmailsender

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Enable and start service
systemctl daemon-reload
systemctl enable fmailsender
systemctl restart fmailsender

echo ""
echo "=== Setup complete! ==="
systemctl status fmailsender --no-pager

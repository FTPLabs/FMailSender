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
      printf "BOT_TOKEN=8869596289:AAFN22KeV6yp8oVCWwDTxu34wEc7Z-HX4bI\nADMIN_IDS=8784635852\nCRYPTO_BOT_TOKEN=594916:AA6n54rTVfzrbCljPW33D49EVwHyDEpmW6f\nHWID_SALT=FMSND-PRODUCTION-SALT-X9K2-2026\nJWT_SECRET=fmsnd-jwt-2026-X9K2M7B4Q3F8W1T5R6Y9P0\nDB_PATH=/opt/fmailsender/server/licenses.db\nAPI_HOST=0.0.0.0\nAPI_PORT=8000\n" > /opt/fmailsender/server/.env
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
  
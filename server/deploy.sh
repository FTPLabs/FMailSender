#!/bin/bash
  # ============================================================
  # FMailSender VPS — Deploy / Update Script
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

  systemctl daemon-reload
  systemctl restart "${SERVICE}"
  sleep 5

  STATUS=$(systemctl is-active "${SERVICE}" 2>/dev/null || echo "unknown")
  if [ "${STATUS}" = "active" ]; then
      echo "✅ Сервис ${SERVICE} ACTIVE"
  else
      echo "❌ Сервис не запустился (status=${STATUS})"
      journalctl -u "${SERVICE}" -n 40 --no-pager
      exit 1
  fi

  echo "[$(date '+%Y-%m-%d %H:%M:%S')] === Deploy complete ==="
  
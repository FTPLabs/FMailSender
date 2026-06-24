#!/bin/bash
# setup_nginx_ratelimit.sh — добавляет rate limiting zones в /etc/nginx/nginx.conf
# Запускай один раз после деплоя: sudo bash scripts/setup_nginx_ratelimit.sh
# Требует root или sudo. Делает backup перед изменением.

set -euo pipefail

NGINX_CONF="/etc/nginx/nginx.conf"
MARKER="fmailsender_rate_zones"

echo "=== Nginx Rate Limiting Setup для fmail.shop ==="

# Проверяем что nginx установлен
command -v nginx >/dev/null 2>&1 || { echo "❌ nginx не найден!"; exit 1; }

# Проверяем что зоны ещё не добавлены
if grep -q "$MARKER" "$NGINX_CONF" 2>/dev/null; then
  echo "✅ Rate limiting zones уже настроены в $NGINX_CONF"
  nginx -t && echo "✅ nginx config: OK"
  exit 0
fi

# Создаём резервную копию
BACKUP="${NGINX_CONF}.bak.$(date +%Y%m%d_%H%M%S)"
cp "$NGINX_CONF" "$BACKUP"
echo "📦 Резервная копия: $BACKUP"

# Вставляем rate limiting zones через python3
python3 - <<'PYEOF'
import sys

with open("/etc/nginx/nginx.conf", "r") as f:
    content = f.read()

zones = """
    # fmailsender_rate_zones
    limit_req_zone  $binary_remote_addr zone=api_verify:10m   rate=10r/m;
    limit_req_zone  $binary_remote_addr zone=api_activate:10m rate=3r/m;
    limit_req_zone  $binary_remote_addr zone=api_download:10m rate=20r/m;
    limit_req_zone  $binary_remote_addr zone=admin_panel:10m  rate=20r/h;
    limit_conn_zone $binary_remote_addr zone=conn_limit:10m;
    limit_req_status 429;
"""

# Ищем закрывающую } блока http {}
# Вставляем rate zones перед последней } в файле
last_brace = content.rfind("}")
if last_brace == -1:
    print("❌ Не найдена закрывающая скобка http{} в nginx.conf")
    sys.exit(1)

new_content = content[:last_brace] + zones + "\n}\n"

with open("/etc/nginx/nginx.conf", "w") as f:
    f.write(new_content)

print("✅ Rate limiting zones добавлены")
PYEOF

# Тестируем и перезагружаем nginx
echo ""
echo "=== Проверка nginx конфигурации ==="
if nginx -t 2>&1; then
  echo "✅ Конфигурация валидна — перезагружаем nginx..."
  nginx -s reload
  echo "✅ nginx перезагружен с rate limiting"
else
  echo "❌ Ошибка конфигурации! Восстанавливаем резервную копию..."
  cp "$BACKUP" "$NGINX_CONF"
  nginx -s reload
  echo "♻️ Резервная копия восстановлена"
  exit 1
fi

echo ""
echo "=== Rate Limiting активен ==="
echo "  /v1/verify   — 10 req/min per IP (burst=5)"
echo "  /v1/activate — 3 req/min per IP  (burst=2)"
echo "  /v1/download — 20 req/min per IP (burst=5)"
echo "  /admin       — 20 req/hour per IP (burst=5)"

#!/bin/bash
# FMailSender — мониторинг всех сервисов
# Использование: bash /opt/fmailsender/server/check_services.sh [--json]
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'; BOLD='\033[1m'
JSON_MODE=0
[[ "${1:-}" == "--json" ]] && JSON_MODE=1

ok()   { [[ $JSON_MODE == 0 ]] && echo -e "${GREEN}✓${NC} $1" || true; }
fail() { [[ $JSON_MODE == 0 ]] && echo -e "${RED}✗${NC} $1" || true; }
warn() { [[ $JSON_MODE == 0 ]] && echo -e "${YELLOW}!${NC} $1" || true; }

check_svc() {
  local name="$1" svc="$2"
  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    ok "$name — активен ($(systemctl show "$svc" --property=MainPID --value | head -1 | xargs -I{} sh -c 'ps -p {} -o etimes= 2>/dev/null | tr -d " " || echo "?"')s uptime)"
    echo "1"
  else
    fail "$name — НЕ ЗАПУЩЕН"
    echo "0"
  fi
}

check_port() {
  local name="$1" port="$2"
  if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
    ok "$name — порт $port слушает"
    echo "1"
  else
    fail "$name — порт $port НЕ слушает"
    echo "0"
  fi
}

check_http() {
  local name="$1" url="$2"
  local code
  code=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
  if [[ "$code" =~ ^[23] ]]; then
    ok "$name — HTTP $code ($url)"
    echo "1"
  else
    fail "$name — HTTP $code ($url)"
    echo "0"
  fi
}

check_downloads() {
  local dl_dir="/opt/fmailsender/server/downloads"
  if [[ ! -d "$dl_dir" ]]; then fail "Downloads dir — НЕ СУЩЕСТВУЕТ ($dl_dir)"; echo "0"; return; fi
  local count; count=$(find "$dl_dir" -maxdepth 1 -type f \( -name "*.exe" -o -name "*.zip" \) | wc -l)
  if [[ $count -gt 0 ]]; then
    ok "Downloads — $count файл(ов) доступно"
    find "$dl_dir" -maxdepth 1 -type f \( -name "*.exe" -o -name "*.zip" \) -exec ls -lh {} \; | awk '{print "  → "$NF" ("$5")"}'
    echo "1"
  else
    warn "Downloads — директория пуста (загрузите .exe/.zip через бота)"
    echo "0"
  fi
}

[[ $JSON_MODE == 0 ]] && echo -e "\n${BOLD}═══════════════════════════════════════${NC}"
[[ $JSON_MODE == 0 ]] && echo -e "${BOLD}  FMailSender — Проверка сервисов${NC}"
[[ $JSON_MODE == 0 ]] && echo -e "${BOLD}  $(date '+%Y-%m-%d %H:%M:%S')${NC}"
[[ $JSON_MODE == 0 ]] && echo -e "${BOLD}═══════════════════════════════════════${NC}\n"

# Collect results
r_bot=$(check_svc "fmailsender (bot+api)" "fmailsender" 2>/dev/null | tail -1)
r_nginx=$(check_svc "nginx" "nginx" 2>/dev/null | tail -1)
r_port8000=$(check_port "Uvicorn" "8000" 2>/dev/null | tail -1)
r_port80=$(check_port "HTTP (nginx)" "80" 2>/dev/null | tail -1)
r_port443=$(check_port "HTTPS (nginx)" "443" 2>/dev/null | tail -1)

[[ $JSON_MODE == 0 ]] && echo ""
r_local=$(check_http "API local" "http://127.0.0.1:8000/health" 2>/dev/null | tail -1)
r_https=$(check_http "fmail.shop HTTPS" "https://fmail.shop/health" 2>/dev/null | tail -1)
r_root=$(check_http "fmail.shop /" "https://fmail.shop/" 2>/dev/null | tail -1)

[[ $JSON_MODE == 0 ]] && echo ""
r_dl=$(check_downloads 2>/dev/null | tail -1)

[[ $JSON_MODE == 0 ]] && echo ""
total=$((r_bot + r_nginx + r_port8000 + r_port80 + r_port443 + r_local + r_https + r_root + r_dl))
all=9
if [[ $total -eq $all ]]; then
  [[ $JSON_MODE == 0 ]] && echo -e "${GREEN}${BOLD}Все $all/$all проверок пройдены ✓${NC}"
else
  [[ $JSON_MODE == 0 ]] && echo -e "${RED}${BOLD}Пройдено $total/$all проверок — есть проблемы!${NC}"
fi
[[ $JSON_MODE == 0 ]] && echo ""

if [[ $JSON_MODE == 1 ]]; then
  echo "{\"fmailsender\":$r_bot,\"nginx\":$r_nginx,\"port_8000\":$r_port8000,\"port_80\":$r_port80,\"port_443\":$r_port443,\"api_local\":$r_local,\"https\":$r_https,\"root_page\":$r_root,\"downloads\":$r_dl,\"passed\":$total,\"total\":$all}"
fi

[[ $total -eq $all ]] && exit 0 || exit 1

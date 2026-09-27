#!/usr/bin/env bash
# Universal Document OS — status check (docker, ports, .env, live /api/status)
set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
ok() { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err() { echo -e "${RED}❌ $1${NC}"; }
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

echo -e "${BOLD}${BLUE}📊 Universal Document OS — status${NC}"
echo ""

# ---------- Docker ----------
echo -e "${BOLD}🐳 Docker${NC}"
if command -v docker &> /dev/null; then
  ok "Docker: $(docker --version)"
  docker compose ps 2>/dev/null || warn "docker compose ps failed — service may be down — try ./start.sh"
else
  err "Docker missing — https://docs.docker.com/get-docker/"
fi
echo ""

# ---------- Ports ----------
echo -e "${BOLD}🌐 Ports${NC}"
if command -v lsof &> /dev/null; then
  if lsof -i :8000 &> /dev/null; then ok "port 8000 — in use (expected)"; else warn "port 8000 — free (service down?)"; fi
elif command -v ss &> /dev/null; then
  if ss -tuln | grep -q ":8000 "; then ok "port 8000 — in use"; else warn "port 8000 — free"; fi
else
  info "cannot check ports (lsof/ss missing)"
fi
echo ""

# ---------- .env (this project's real variables only) ----------
echo -e "${BOLD}🔑 .env${NC}"
if [ -f .env ]; then
  ok ".env exists ($(wc -l < .env) lines)"
  perms=$(stat -c %a .env 2>/dev/null || stat -f %A .env 2>/dev/null || echo "unknown")
  if [ "$perms" = "600" ]; then
    ok ".env permissions 600"
  else
    warn ".env permissions $perms — fixing to 600"
    chmod 600 .env 2>/dev/null && ok "fixed" || warn "could not chmod"
  fi
  # Only variables this codebase actually reads.
  for var in PORT SMS_PROVIDER NOTIF_TELEGRAM LOG_LEVEL; do
    grep -q "^${var}=" .env && info "$var is set" || info "$var not set (defaults apply)"
  done
  if grep -q "^UDO_API_KEYS=..*" .env; then
    ok "UDO_API_KEYS set — API authentication is ON"
  else
    warn "UDO_API_KEYS empty — API is open to anyone who can reach the port (fine for localhost)"
  fi
  if grep -q "^RATE_LIMIT_PER_MIN=[1-9]" .env; then
    ok "RATE_LIMIT_PER_MIN set — rate limiting is ON"
  else
    warn "RATE_LIMIT_PER_MIN off — no rate limiting"
  fi
else
  err ".env missing — run ./install.sh"
fi
echo ""

# ---------- Health + live status ----------
echo -e "${BOLD}❤️ Health & live counters${NC}"
if command -v curl &> /dev/null; then
  if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
    ok "http://localhost:8000/api/health — UP"
    if command -v python3 &> /dev/null; then
      curl -s http://localhost:8000/api/status | python3 -m json.tool 2>/dev/null || true
    else
      curl -s http://localhost:8000/api/status || true
    fi
  else
    warn "http://localhost:8000/api/health — no response — wait 30s or run ./logs.sh"
  fi
  if curl -sf http://localhost:8000/app >/dev/null 2>&1; then
    ok "http://localhost:8000/app (panel + smart dashboard) — UP"
  else
    warn "http://localhost:8000/app — no response"
  fi
else
  info "curl missing — cannot probe health"
fi
echo ""

# ---------- Disk + memory ----------
echo -e "${BOLD}💾 Disk & memory${NC}"
if command -v df &> /dev/null; then
  df -h . | tail -n 1 | awk '{print "  disk: " $4 " free of " $2 " (" $5 " used)"}'
  usage=$(df . | tail -n 1 | awk '{print $5}' | sed 's/%//')
  [ "$usage" -gt 80 ] && warn "  disk ${usage}% full — old backups: ./backup.sh keeps 7" || ok "  disk ok"
fi
if command -v free &> /dev/null; then
  free -h | grep Mem | awk '{print "  memory: " $3 " used of " $2}'
fi
echo ""

echo -e "${BOLD}🛠️ Commands${NC}"
echo "  ./logs.sh · ./stop.sh / ./start.sh · ./update.sh · ./backup.sh · ./smoke-test.sh"
echo ""

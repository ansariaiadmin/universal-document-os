#!/usr/bin/env bash
# Universal Document OS — installer (Docker)
# Preflight (docker/disk/port) -> generate .env from .env.example -> build -> start -> wait for health.
set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
ok() { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err() { echo -e "${RED}❌ $1${NC}"; }
info() { echo -e "${CYAN}   💡 $1${NC}"; }

echo -e "${BOLD}${BLUE}Universal Document OS — installer${NC}"
echo ""

# ---------- [1/4] Preflight ----------
echo -e "${BLUE}[1/4] 🐳 Docker${NC}"
if ! command -v docker &> /dev/null; then
  err "Docker is missing — https://docs.docker.com/get-docker/"
  exit 1
fi
ok "Docker: $(docker --version)"
if ! docker info &> /dev/null; then
  err "Docker daemon is not running — start Docker Desktop / dockerd first"
  exit 1
fi
ok "Compose: $(docker compose version)"

if command -v df &> /dev/null; then
  usage=$(df . | tail -n 1 | awk '{print $5}' | sed 's/%//')
  if [ "$usage" -gt 80 ]; then
    warn "disk ${usage}% full — consider cleaning up before building"
  else
    ok "disk ok (${usage}% used)"
  fi
fi

if command -v lsof &> /dev/null; then
  if lsof -i :8000 &> /dev/null; then
    warn "port 8000 is busy — set a different PORT in .env (host mapping)"
  else
    ok "port 8000 free"
  fi
fi

# ---------- [2/4] .env ----------
echo ""
echo -e "${BLUE}[2/4] 🔑 .env${NC}"
if [ -f .env ]; then
  read -p "   .env already exists — keep it? (Y/n): " keep
  case "$keep" in
    n|N)
      cp .env ".env.backup.$(date +%Y%m%d_%H%M%S)"
      ok "backed up the old .env"
      cp .env.example .env
      ok "fresh .env created from .env.example"
      ;;
    *) ok "keeping the existing .env" ;;
  esac
else
  cp .env.example .env
  ok ".env created from .env.example"
fi
chmod 600 .env 2>/dev/null && ok ".env permissions set to 600" || warn "could not chmod 600 .env"

echo ""
info "Security is opt-in: set UDO_API_KEYS=key1,key2 in .env to require an X-API-Key"
info "on every /api/* call, and RATE_LIMIT_PER_MIN=60 to rate-limit. Local dev can leave them empty."

# ---------- [3/4] Build & start ----------
echo ""
echo -e "${BLUE}[3/4] 🏗️  Build & start${NC}"
docker compose up --build -d

echo ""
echo -e "${BLUE}[4/4] ⏳ Waiting for health check${NC}"
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
    ok "service is healthy"
    break
  fi
  printf "."
  sleep 1
done
echo ""
docker compose ps 2>/dev/null || true

if ! curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
  err "health check did not pass within 30s — run ./logs.sh to see why"
  exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 Universal Document OS is ready${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BOLD}📍 URLs:${NC}"
echo -e "${GREEN}  🌐 http://localhost:8000        — landing page${NC}"
echo -e "${GREEN}  📊 http://localhost:8000/app    — panel + smart dashboard${NC}"
echo -e "${GREEN}  📚 http://localhost:8000/api/docs — Swagger UI${NC}"
echo -e "${GREEN}  ❤️  http://localhost:8000/api/health — health check${NC}"
echo ""
echo "Daily commands: ./status.sh · ./logs.sh · ./stop.sh · ./start.sh · ./update.sh · ./backup.sh · ./smoke-test.sh"

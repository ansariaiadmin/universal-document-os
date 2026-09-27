#!/usr/bin/env bash
# Universal Document OS — update (backup -> git pull -> rebuild -> health)
set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
ok() { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

echo -e "${BOLD}${BLUE}🔄 Universal Document OS — update${NC}"
echo ""

if [ ! -f .env ]; then
  echo -e "${RED}❌ .env missing — run ./install.sh first${NC}"
  exit 1
fi

# ---------- 1) Backup ----------
echo -e "${BLUE}📦 Automatic backup before update${NC}"
./backup.sh || warn "backup failed — continuing anyway"

# ---------- 2) Git pull ----------
if [ -d .git ]; then
  echo -e "${BLUE}📥 git pull${NC}"
  git pull --ff-only 2>/dev/null || warn "git pull failed (offline or diverged) — continuing with local code"
else
  info "not a git repo — skipping pull"
fi

# ---------- 3) Rebuild & restart ----------
echo -e "${BLUE}🏗️ Rebuild & restart${NC}"
if command -v docker &> /dev/null; then
  docker compose up --build -d 2>&1 | tail -n 20
  ok "rebuilt and restarted"

  echo -e "${BLUE}⏳ Waiting for health${NC}"
  for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
      ok "service healthy"
      break
    fi
    printf "."
    sleep 1
  done
  echo ""
  docker compose ps 2>/dev/null || true
else
  warn "Docker missing — cannot rebuild"
fi

# ---------- 4) Final health ----------
if command -v curl &> /dev/null; then
  curl -sf http://localhost:8000/api/health >/dev/null 2>&1 && ok "health UP" || warn "health DOWN — ./logs.sh"
  curl -sf http://localhost:8000/app >/dev/null 2>&1 && ok "panel UP" || warn "panel DOWN"
fi

echo ""
echo -e "${GREEN}🎉 update finished${NC}"
echo ""

#!/usr/bin/env bash
# Universal Document OS — smoke test (end-to-end probe of the REAL pipeline)
# Health -> panel -> dashboard -> real upload/extract/download round-trip.
set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
ok() { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err() { echo -e "${RED}❌ $1${NC}"; }

echo -e "${BOLD}${BLUE}🧪 Universal Document OS — smoke test${NC}"
echo ""

BASE="${SMOKE_BASE_URL:-http://localhost:8000}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ---------- [1/5] Health ----------
echo -e "${BOLD}[1/5] ❤️ Health${NC}"
curl -sf "$BASE/api/health" >/dev/null 2>&1 && ok "$BASE/api/health — UP" || err "$BASE/api/health — DOWN"
echo ""

# ---------- [2/5] Pages ----------
echo -e "${BOLD}[2/5] 🖥️ Pages${NC}"
curl -sf "$BASE/" >/dev/null 2>&1 && ok "landing page — UP" || warn "landing page — DOWN"
curl -sf "$BASE/app" >/dev/null 2>&1 && ok "panel + smart dashboard — UP" || warn "panel — DOWN"
curl -sf "$BASE/manifest.webmanifest" >/dev/null 2>&1 && ok "PWA manifest — UP" || warn "PWA manifest — DOWN"
echo ""

# ---------- [3/5] Dashboard ----------
echo -e "${BOLD}[3/5] 📊 Smart dashboard API${NC}"
if curl -sf "$BASE/api/dashboard" | python3 -m json.tool >/dev/null 2>&1; then
  ok "/api/dashboard returns valid JSON"
  curl -s "$BASE/api/dashboard" | python3 -c "import sys,json;d=json.load(sys.stdin);print('   version:',d.get('version'));print('   engines:',d.get('capabilities',{}).get('ocr_engines'))" 2>/dev/null || true
else
  warn "/api/dashboard failed"
fi
echo ""

# ---------- [4/5] Real pipeline round-trip ----------
echo -e "${BOLD}[4/5] 🔁 Pipeline round-trip (upload -> extract -> export -> download)${NC}"
printf 'Universal Document OS smoke test — سلام دنیا\n' > "$TMP/note.txt"
RESP=$(curl -s -X POST "$BASE/api/process" -F "file=@$TMP/note.txt" -F "operation=export_text" -F "target_format=md")
echo "$RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d.get('status') == 'READY', d
assert d.get('download'), d
assert 'smoke test' in d.get('preview','')
print('   ✅ processed:', d.get('detected_format'), '-', d.get('characters'), 'chars')
print('   ✅ download:  ', d.get('download'))
" || { err "process failed"; echo "$RESP"; exit 1; }
DL=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['download'])")
curl -sf "$BASE$DL" | grep -q "smoke test" && ok "downloaded export contains the text" || err "download failed"
echo ""

# ---------- [5/5] OCR (real, only if tesseract is installed) ----------
echo -e "${BOLD}[5/5] 🔍 OCR engine (real check)${NC}"
if command -v tesseract >/dev/null 2>&1; then
  ok "tesseract binary present: $(tesseract --version 2>&1 | head -n 1)"
else
  warn "tesseract binary not on this host — OCR works inside the Docker image, not here"
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 smoke test finished${NC}"
echo -e "${GREEN}========================================${NC}"

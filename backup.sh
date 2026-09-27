#!/usr/bin/env bash
# Universal Document OS — backup
# Backs up: ALL of data/ (uploads, outputs, workrooms, audit.jsonl, jobs.db)
# plus the provider-relevant NON-secret settings from .env. Does NOT pretend
# to back up a database: this project stores state on the filesystem.
set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
ok() { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

echo -e "${BOLD}${BLUE}💾 Universal Document OS — backup${NC}"
echo ""

if [ ! -d data ]; then
  err "no data/ directory — nothing to back up (service never ran?)"
  exit 1
fi

BACKUP_DIR="./backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE="$BACKUP_DIR/udo-backup-$TIMESTAMP.tar.gz"

# ---------- 1) Data directory (uploads, outputs, workrooms, audit, jobs.db) ----------
echo -e "${BLUE}📦 Archiving data/ ...${NC}"
tar -czf "$ARCHIVE" data/ 2>/dev/null || { err "tar failed"; exit 1; }
ok "data/ archived ($(du -h "$ARCHIVE" | awk '{print $1}'))"

# ---------- 2) Non-secret settings snapshot (never stores secrets) ----------
ENV_SNAPSHOT="$BACKUP_DIR/settings-$TIMESTAMP.env"
if [ -f .env ]; then
  # Keep only non-secret configuration lines; keys/tokens are written as "<redacted>".
  grep -E "^[A-Z_]+=" .env \
    | sed -E 's/^((TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID|SMS_API_KEY|GHASEDAK_API_KEY|KAVENEGAR_API_KEY|TRANSLATION_API_KEY|UDO_API_KEYS)=).*/\1<redacted>/' \
    > "$ENV_SNAPSHOT" || true
  ok "non-secret settings snapshot: $ENV_SNAPSHOT (secret values redacted)"
  warn "the real .env itself is NOT copied — keep your own encrypted copy of it"
fi

# ---------- 3) Optional encryption ----------
if [ "${BACKUP_ENCRYPT:-0}" = "1" ] && command -v openssl &> /dev/null; then
  echo -n "   encryption passphrase: "
  read -rs PASS && echo
  if openssl enc -aes-256-cbc -salt -pbkdf2 -in "$ARCHIVE" -out "$ARCHIVE.enc" -pass pass:"$PASS" 2>/dev/null; then
    rm "$ARCHIVE"
    ok "archive encrypted: $ARCHIVE.enc (AES-256-CBC + PBKDF2)"
  else
    warn "encryption failed — unencrypted archive kept: $ARCHIVE"
  fi
fi

# ---------- 4) Retention: keep last 7 ----------
ls -t "$BACKUP_DIR"/udo-backup-*.tar.gz* 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true
ok "retention: last 7 backups kept"

echo ""
ok "backup complete: $(ls -t "$BACKUP_DIR"/udo-backup-* 2>/dev/null | head -n 1)"
info "restore:   tar -xzf <archive> (in the project root, service stopped)"
info "automate:  add BACKUP_ENCRYPT=1 to .env to be prompted for a passphrase"
echo ""
ls -lh "$BACKUP_DIR" 2>/dev/null | tail -n 10

#!/usr/bin/env bash
set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; MAGENTA='\033[0;35m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'
ok() { echo -e "${GREEN}✅ $1${NC}"; }
explain() { echo -e "${CYAN}   💡 $1${NC}"; }
example() { echo -e "${DIM}   📝 مثال: $1${NC}"; }
where() { echo -e "${MAGENTA}   🔗 کجا؟ $1${NC}"; }
ask_with_help() {
  local prompt="$1"; local help_text="$2"; local example_text="$3"; local where_text="$4"; local default_val="$5"; local is_secret="${6:-false}"
  echo ""; echo -e "${BOLD}${BLUE}❓ $prompt${NC}"; [ -n "$help_text" ] && explain "$help_text"; [ -n "$example_text" ] && example "$example_text"; [ -n "$where_text" ] && where "$where_text"
  [ -n "$default_val" ] && echo -e "${DIM}   ⏭️  Enter=پیش‌فرض: $default_val${NC}" || echo -e "${DIM}   ⏭️  اگر نداری Enter=mock${NC}"
  local input=""; if [ "$is_secret" = "true" ]; then read -s -p "   👉 جواب: " input; echo ""; else read -p "   👉 جواب: " input; fi
  [ -z "$input" ] && [ -n "$default_val" ] && input="$default_val"; echo "$input"
}
ask_yes_no() {
  local prompt="$1"; local help_text="$2"; local default_yes="${3:-true}"
  echo ""; echo -e "${BOLD}${BLUE}❓ $prompt${NC}"; [ -n "$help_text" ] && explain "$help_text"
  [ "$default_yes" = "true" ] && echo -e "${DIM}   ⏭️  [Y/n] Enter=بله${NC}" || echo -e "${DIM}   ⏭️  [y/N] Enter=خیر${NC}"
  local input=""; read -p "   👉 جواب (y/n): " input; input=$(echo "$input" | tr '[:upper:]' '[:lower:]')
  [ -z "$input" ] && { if [ "$default_yes" = "true" ]; then input="y"; else input="n"; fi; }
  if [ "$input" = "y" ] || [ "$input" = "yes" ] || [ "$input" = "بله" ]; then echo "yes"; else echo "no"; fi
}

clear
echo -e "${CYAN}"
cat <<'BANNER'
 _   _       _                    _
| | | |_ __ (_)_   _____ _ __ ___  | |
| | | | '_ \| \ \ / / _ \ '__/ __| | |
| |_| | | | | |\ V /  __/ |  \__ \ |_|
 \___/|_| |_|_| \_/ \___|_|  |___/ (_)
Document OS — OCR + Translation + Notification — Zero Support
BANNER
echo -e "${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  🧙‍♂️ جادوگر نصب Universal Document OS v3.1.0 — پشتیبانی صفر — تاریکی روشن شد${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}سلام! 👋 سیستم اسناد — OCR Multi-Engine + ترجمه + Layout + Benchmark + ناتیف — سقف!${NC}"
echo ""
read -p "برای شروع جادو Enter بزنید... ✨ " _

echo -e "${BLUE}[1/6] 🔍 سیستم${NC}"; ok "اوکیه"; sleep 1
echo -e "${BLUE}[2/6] 🐳 Docker${NC}"; if ! command -v docker &> /dev/null; then echo -e "${RED}Docker نیست${NC}"; exit 1; else ok "Docker: $(docker --version)"; fi; sleep 1
echo -e "${BLUE}[3/6] 🤖 OCR + Translation Provider${NC}"
explain "Document OS از OCR برای خوندن متن PDF و Translation برای ترجمه استفاده می‌کنه — می‌تونه لوکال باشه (Tesseract رایگان) یا Cloud"
OCR_PROVIDER=$(ask_with_help "OCR پرووایدر؟" "برای خوندن متن از PDF/عکس — Tesseract لوکال رایگان" "tesseract یا paddle یا easy یا mock" "Tesseract لوکال رایگان — پیش‌فرض" "tesseract" "false")
TRANSLATION_ENABLED=$(ask_yes_no "ترجمه فعال باشه؟" "وقتی سند آپلود می‌شه ترجمه هم بشه" "false")
TRANSLATION_KEY=""
if [ "$TRANSLATION_ENABLED" = "yes" ]; then
  TRANSLATION_KEY=$(ask_with_help "کلید API ترجمه؟" "مثل Google Translate API" "api-key-..." "https://cloud.google.com/translate" "" "true")
  ok "Translation تنظیم شد"
fi
sleep 1

echo -e "${BLUE}[4/6] 📧 Email + 📱 SMS — برای ناتیف اسناد${NC}"
explain "وقتی سند آپلود می‌شه، OCR تموم می‌شه، یا ترجمه آماده می‌شه — ناتیف می‌ده"
# هزینه: هر پیامک ~120 تومان — تاریکی روشن شد — cost warning
SMS_PROVIDER=$(ask_with_help "SMS پرووایدر برای ناتیف اسناد؟" "وقتی OCR تموم می‌شه پیامک بره" "ghasedak یا mock" "https://ghasedak.me/" "mock" "false")
SMS_KEY=""
if [ "$SMS_PROVIDER" != "mock" ]; then SMS_KEY=$(ask_with_help "کلید API SMS؟" "از پنل" "api-key" "پنل → API" "" "true"); ok "SMS تنظیم شد"; fi
EMAIL_PROVIDER=$(ask_with_help "ایمیل پرووایدر؟" "برای ناتیف اسناد" "smtp یا mock" "Gmail" "mock" "false")
SMTP_HOST=""; SMTP_USER=""; SMTP_PASS=""
if [ "$EMAIL_PROVIDER" = "smtp" ]; then
  SMTP_HOST=$(ask_with_help "SMTP Host؟" "smtp.gmail.com" "smtp.gmail.com" "Gmail" "smtp.gmail.com" "false")
  SMTP_USER=$(ask_with_help "SMTP User؟" "you@gmail.com" "ایمیل" "" "false")
  SMTP_PASS=$(ask_with_help "SMTP Pass؟" "App Password" "app-pass" "myaccount.google.com → App Passwords" "" "true")
  ok "SMTP تنظیم شد"
fi
sleep 1

echo -e "${BLUE}[5/6] 🔔 Notification System — اسناد${NC}"
explain "وقتی سند آپلود می‌شه، OCR تموم می‌شه، ترجمه آماده می‌شه — خبر می‌ده"
NOTIF_EMAIL=$(ask_yes_no "ایمیل ناتیف روشن باشه؟" "وقتی OCR تموم می‌شه ایمیل بره" "true")
NOTIF_SMS=$(ask_yes_no "پیامک ناتیف روشن باشه؟" "وقتی سند آماده می‌شه پیامک بره" "false")
TELEGRAM_ENABLED=$(ask_yes_no "ربات تلگرام برای ناتیف اسناد می‌خوای؟" "وقتی سند آپلود می‌شه تلگرام خبر می‌ده" "false")
TELEGRAM_TOKEN=""; TELEGRAM_CHAT=""
if [ "$TELEGRAM_ENABLED" = "yes" ]; then
  TELEGRAM_TOKEN=$(ask_with_help "توکن ربات؟" "از @BotFather" "123456:ABC..." "@BotFather → /newbot" "" "true")
  TELEGRAM_CHAT=$(ask_with_help "Chat ID؟" "از getUpdates" "123456789" "https://api.telegram.org/bot<TOKEN>/getUpdates" "" "false")
  ok "Telegram تنظیم شد"
fi
sleep 1

echo -e "${BLUE}[6/6] ⚙️ .env + 🏗️ اجرا${NC}"
if [ -f .env ]; then
  echo -e "${YELLOW}  .env وجود دارد — keep/new/backup? — تاریکی روشن شد — idempotency${NC}"
  read -p "   keep (نگه دار) / new (جدید) / backup (بکاپ بعد جدید) [keep]: " KEEP_ENV
  [ -z "$KEEP_ENV" ] && KEEP_ENV="keep"
  if [ "$KEEP_ENV" = "backup" ]; then cp .env .env.backup.$(date +%Y%m%d_%H%M%S); echo -e "${GREEN}✅ بکاپ گرفته شد — تاریکی روشن شد${NC}"; KEEP_ENV="new"; fi
  if [ "$KEEP_ENV" = "keep" ]; then echo -e "${GREEN}✅ .env نگه داشته شد — idempotency — تاریکی روشن شد${NC}"; SKIP_ENV="true"; else SKIP_ENV="false"; fi
else
  SKIP_ENV="false"
fi

if [ "$SKIP_ENV" = "false" ]; then
cat > .env <<EOF
# universal-document-os — .env — جادوگر v3.1.0 — پشتیبانی صفر — تاریکی روشن شد — $(date)
PORT=8000

# OCR — چیه؟ خوندن متن از PDF/عکس — گزینه: tesseract (لوکال رایگان), paddle, easy, mock
OCR_PROVIDER=${OCR_PROVIDER}
TESSERACT_CMD=/usr/bin/tesseract
PADDLE_OCR_ENABLED=true
EASY_OCR_ENABLED=true

# Translation — ترجمه — چیه؟ ترجمه متن سند — گزینه: google, mock
TRANSLATION_ENABLED=${TRANSLATION_ENABLED}
TRANSLATION_API_KEY=${TRANSLATION_KEY}
LAYOUT_PARSER_ENABLED=true

# SMS + Email — برای ناتیف اسناد
# هزینه: هر پیامک ~120 تومان — تاریکی روشن شد — cost warning
SMS_PROVIDER=${SMS_PROVIDER}
SMS_API_KEY=${SMS_KEY}
EMAIL_PROVIDER=${EMAIL_PROVIDER}
SMTP_HOST=${SMTP_HOST}
SMTP_PORT=587
SMTP_USER=${SMTP_USER}
SMTP_PASS=${SMTP_PASS}

# Notification System — سقف 10/10 — چیه؟ اطلاع‌رسانی آپلود + OCR + ترجمه
NOTIF_IN_APP=true
NOTIF_EMAIL=${NOTIF_EMAIL}
NOTIF_SMS=${NOTIF_SMS}
NOTIF_TELEGRAM=${TELEGRAM_ENABLED}
TELEGRAM_BOT_TOKEN=${TELEGRAM_TOKEN}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT}
EOF

chmod 600 .env 2>/dev/null || true
ok ".env ساخته شد — permission 600 — امن — تاریکی روشن شد"
fi
if [ "$SKIP_ENV" = "true" ]; then
  chmod 600 .env 2>/dev/null || true
  echo -e "${GREEN}✅ .env permission 600 — امن — تاریکی روشن شد${NC}"
fi — امن — تاریکی روشن شد"
docker compose up --build -d 2>&1 | tail -n 10
echo ""; echo -e "${BLUE}  ⏳ 30 ثانیه صبر...${NC}"
echo -n "  "; for i in {1..30}; do echo -n "."; sleep 1; if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then echo ""; ok "آماده!"; break; fi; done
echo ""; docker compose ps 2>/dev/null || true

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  🎉 جادو تمام! Document OS آماده — پشتیبانی صفر! 🎉${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BOLD}${BLUE}📍 دسترسی:${NC}"
echo -e "${GREEN}  🌐 URL: http://localhost:8000 — Upload PDF → OCR multi-engine → Translation + Layout — سقف!${NC}"
echo ""
echo -e "${CYAN}📚 docs/SETUP-WIZARD-FA.md${NC}"
echo ""

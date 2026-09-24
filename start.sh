#!/usr/bin/env bash
set -e
echo "شروع Universal Document OS — Document Processing / Starting Universal Document OS — Document Processing..."
if [ -f docker-compose.yml ]; then
  docker compose up -d
  docker compose ps
  echo "✓ اجرا شد / Started - http://localhost:8000 (Landing) و http://localhost:8000/app (Panel)"
else
  echo "برای CLI: ./project-robots --help یا source .venv/bin/activate && python -m app.main"
  if [ -f package.json ]; then npm run dev; fi
fi

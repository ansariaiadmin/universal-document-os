#!/usr/bin/env bash
set -e
echo "توقف Universal Document OS — Document Processing / Stopping..."
if [ -f docker-compose.yml ]; then
  docker compose down
  echo "✓ متوقف شد / Stopped"
else
  echo "برای توقف Ctrl+C بزنید / Press Ctrl+C to stop"
  docker compose down 2>/dev/null || true
fi

#!/usr/bin/env bash
# Universal Document OS — logs
if [ -f docker-compose.yml ] && command -v docker &> /dev/null; then
  docker compose logs --tail=100 -f
else
  echo "Docker not available — native run logs go to the terminal that started uvicorn (see run.sh)."
  ls -lh logs/ 2>/dev/null || true
fi

#!/usr/bin/env bash
# Universal Document OS — start (docker compose)
set -e
if [ -f docker-compose.yml ]; then
  docker compose up -d
  docker compose ps
  echo "✓ http://localhost:8000 (landing) · http://localhost:8000/app (panel + smart dashboard)"
else
  echo "docker-compose.yml not found — run from the project root, or use run.sh for a native venv server"
fi

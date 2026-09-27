#!/usr/bin/env bash
# Universal Document OS — stop (docker compose)
set -e
if [ -f docker-compose.yml ]; then
  docker compose down
  echo "✓ stopped"
else
  echo "docker-compose.yml not found — nothing to stop"
fi

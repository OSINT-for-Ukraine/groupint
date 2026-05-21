#!/usr/bin/env sh
# Run Groupint on Docker Desktop (not system dockerd).
set -e
cd "$(dirname "$0")/.."
unset DOCKER_HOST
docker context use desktop-linux 2>/dev/null || true
docker network create groupint-net 2>/dev/null || true
APP_NAME=groupint docker compose -f docker-compose.desktop.yml up -d --build "$@"

echo ""
echo "Groupint (Docker Desktop):"
echo "  App:   http://localhost:18501  (8501 if you cleared stale docker-proxy on the host)"
echo "  Neo4j: http://localhost:17474"

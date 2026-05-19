#!/usr/bin/env bash
# One-time wipe of Groupint Neo4j data volumes (destructive).
# Groupint docker-compose.desktop.yml has Neo4j only — no Postgres in this stack.
# To remove another project's Postgres volume, e.g. flowsint-dev_pg_data_dev:
#   docker volume rm -f flowsint-dev_pg_data_dev

set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.desktop.yml}"

echo "Stopping Groupint stack..."
docker compose -f "$COMPOSE_FILE" down

echo "Removing Neo4j volumes..."
docker volume rm -f \
  groupint_groupint-neo4j-data \
  groupint_groupint-neo4j-logs \
  groupint_groupint-neo4j-import \
  groupint_groupint-neo4j-plugins \
  2>/dev/null || true

echo "Starting Groupint stack..."
docker compose -f "$COMPOSE_FILE" up -d

echo "Done. Neo4j is empty; Telegram session volume was not removed."

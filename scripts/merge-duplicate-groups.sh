#!/usr/bin/env bash
# Merge duplicate Group nodes in Neo4j (same chat under different ids).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CONTAINER="${GROUPINT_CONTAINER:-groupint-streamlit}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Container $CONTAINER is not running. Start the stack first (e.g. scripts/up-desktop.sh)." >&2
  exit 1
fi

docker exec "$CONTAINER" python -c "
from db.dal import GraphManager
result = GraphManager.merge_duplicate_groups(ensure_unique_constraint=True)
print('merge_duplicate_groups:', result)
"

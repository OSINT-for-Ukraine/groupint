#!/usr/bin/env sh
# Start Atlos (dev) + Groupint on shared Docker network groupint-net.
set -e
cd "$(dirname "$0")/.."
unset DOCKER_HOST
docker context use desktop-linux 2>/dev/null || true

if [ ! -f vendor/atlos/platform/mix.exs ]; then
  echo "Initializing vendor/atlos submodule…"
  git submodule update --init --depth 1 vendor/atlos 2>/dev/null || {
    mkdir -p vendor
    rm -rf vendor/atlos
    git clone --depth 1 https://github.com/atlosdotorg/atlos.git vendor/atlos
  }
fi

docker network create groupint-net 2>/dev/null || true

echo "Starting Atlos (PostGIS + dev server)…"
APP_NAME=groupint docker compose -f docker-compose.atlos.yml up -d --build

echo "Starting Groupint…"
APP_NAME=groupint docker compose -f docker-compose.desktop.yml up -d --build

echo ""
echo "Full stack:"
echo "  Groupint:  http://localhost:18501"
echo "  Atlos:     http://localhost:13000  (login: admin@localhost.com / localhost123 if seeded)"
echo "  Neo4j:     http://localhost:17474"
echo ""
echo "Set ATLOS_API_TOKEN in .env after creating a token in Atlos → Project → Access."

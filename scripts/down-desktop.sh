#!/usr/bin/env sh
set -e
cd "$(dirname "$0")/.."
unset DOCKER_HOST
docker context use desktop-linux
APP_NAME=groupint docker compose -f docker-compose.desktop.yml down "$@"

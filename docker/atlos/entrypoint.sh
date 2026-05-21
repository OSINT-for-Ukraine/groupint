#!/bin/sh
set -e
cd /app
export MIX_ENV=dev
export PORT="${PORT:-4000}"
export PHX_HOST="${PHX_HOST:-localhost}"
export DEVELOPMENT_MODE="${DEVELOPMENT_MODE:-true}"
export ENABLE_CAPTCHAS="${ENABLE_CAPTCHAS:-false}"

if [ ! -f config/dev.secret.exs ]; then
  cp /docker-atlos/dev.secret.exs config/dev.secret.exs
fi

mix local.hex --force
mix local.rebar --force
mix deps.get
mix ecto.create 2>/dev/null || true
mix ecto.migrate
exec mix phx.server

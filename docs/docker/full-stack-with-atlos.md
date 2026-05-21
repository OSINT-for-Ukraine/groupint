# Docker: full stack with Atlos

Run **Groupint** and a **local Atlos** instance on a shared Docker network for incident export without AWS.

## Quick start

```bash
cp .env.example .env
# Fill TELEGRAM_*, LLM keys; set ATLOS_API_TOKEN after creating token in Atlos
chmod +x scripts/up-full.sh
./scripts/up-full.sh
```

First Atlos image build can take **10–15 minutes** (Elixir dependencies).

## URLs

| Service | URL |
|---------|-----|
| Groupint | http://localhost:18501 |
| Atlos (dev) | http://localhost:13000 |
| Neo4j Browser | http://localhost:17474 |

## Services

| Container | Compose file | Port |
|-----------|--------------|------|
| `groupint-streamlit` | `docker-compose.desktop.yml` | 18501 |
| `groupint-incident-worker` | `docker-compose.desktop.yml` | — |
| `groupint-neo4j` | `docker-compose.desktop.yml` | 17474 / 17687 |
| `groupint-atlos` | `docker-compose.atlos.yml` | 13000 |
| `groupint-atlos-postgres` | `docker-compose.atlos.yml` | internal |

Network: **`groupint-net`** (external; created by the script).

## Atlos (no AWS)

- Source: `vendor/atlos` git submodule ([atlosdotorg/atlos](https://github.com/atlosdotorg/atlos)).
- Image: `docker/atlos/Dockerfile.dev` — `mix phx.server`, `MIX_ENV=dev`.
- Database: PostGIS with `citext` + `postgis` (`docker/atlos/init-db.sql`).
- Uploads: local files under a volume (`priv/uploads`) — no S3 bucket.

[`scripts/up-full.sh`](../../scripts/up-full.sh) initializes `vendor/atlos` via submodule or shallow clone if missing.

## Environment

In `.env` for Groupint containers talking to Atlos on the same network:

```bash
ATLOS_BASE_URL=http://atlos:4000
ATLOS_API_TOKEN=your_token_here
```

From your browser you use http://localhost:13000; inside Docker, Streamlit uses the internal hostname `atlos` on port 4000.

## Atlos API token

1. Open http://localhost:13000 and log in (dev seed may use `admin@localhost.com` / `localhost123` if applicable).
2. Create or open a **project**.
3. **Access** → **API Tokens** → create token with write permission.
4. Set `ATLOS_API_TOKEN` in `.env` or save on the Incidents page.

See [Atlos export](../incidents/atlos-export.md).

## Groupint only (without Atlos)

```bash
./scripts/up-desktop.sh
```

## Next steps

- [Atlos export](../incidents/atlos-export.md)
- [Incidents overview](../incidents/overview.md)

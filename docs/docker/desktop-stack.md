# Docker: desktop stack

The **desktop stack** runs Groupint with Neo4j and a background incident worker. It does not include Atlos.

## Quick start

```bash
cp .env.example .env
# Edit .env: TELEGRAM_*, LLM keys as needed
chmod +x scripts/up-desktop.sh
./scripts/up-desktop.sh
```

## Services

| Container | Compose file | Host ports | Role |
|-----------|--------------|------------|------|
| `groupint-streamlit` | `docker-compose.desktop.yml` | **18501** | Streamlit UI |
| `groupint-neo4j` | `docker-compose.desktop.yml` | **17474** HTTP, **17687** Bolt | Graph database |
| `groupint-incident-worker` | `docker-compose.desktop.yml` | — | Watchlist poll + LLM pipeline |

## URLs

| Service | URL |
|---------|-----|
| Groupint | http://localhost:18501 |
| Neo4j Browser | http://localhost:17474 |

Neo4j uses `NEO4J_AUTH=none` in this stack — no password in Browser or Gephi.

## Script behavior

[`scripts/up-desktop.sh`](../../scripts/up-desktop.sh):

1. Uses Docker context `desktop-linux` when available (Docker Desktop).
2. Creates external network `groupint-net` if missing.
3. Runs `docker compose -f docker-compose.desktop.yml up -d --build`.

## Internal vs host Neo4j

| Client | Bolt URL |
|--------|----------|
| Streamlit / worker (inside Docker) | `bolt://groupint-neo4j:7687` |
| Gephi / tools on your host | `bolt://localhost:17687` |

## Logs and restart

```bash
docker logs -f groupint-streamlit
docker logs -f groupint-incident-worker
docker restart groupint-streamlit
```

Health check:

```bash
curl -sf http://localhost:18501/_stcore/health
```

## Legacy compose

Older [`docker-compose.yml`](../../docker-compose.yml) publishes Streamlit on **8501** and Neo4j on **7474** / **7687**. Prefer the desktop stack for new setups unless you rely on those ports.

## Next steps

- [Sessions and authentication](../telegram/sessions-and-auth.md)
- [Incidents overview](../incidents/overview.md)
- [Full stack with Atlos](full-stack-with-atlos.md) — if you need local Atlos export

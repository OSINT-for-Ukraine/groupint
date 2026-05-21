# Atlos export

Push geocoded **Incident** nodes from Groupint to [Atlos](https://atlos.org) using [API v2](https://docs.atlos.org/technical/api/).

## Prerequisites

- Incidents with coordinates in Neo4j (pipeline completed)
- Atlos reachable from Groupint (local or cloud)
- API token with **write** permission on a project

### Local full stack

```bash
./scripts/up-full.sh
```

| Service | URL |
|---------|-----|
| Groupint | http://localhost:18501 |
| Atlos (dev) | http://localhost:13000 |
| Neo4j | http://localhost:17474 |

Atlos runs without AWS (`MIX_ENV=dev`, local file storage). See [Docker: full stack with Atlos](../docker/full-stack-with-atlos.md).

## Create an API token

1. Open Atlos in the browser.
2. Log in to your project.
3. **Access** → **API Tokens** → create token with write permission.
4. Set in Groupint:
   - `.env`: `ATLOS_API_TOKEN=...`
   - Or Incidents page → **Export to Atlos** → **Save Atlos settings** (stored in Neo4j)

## UI: Export to Atlos

On the Incidents page, section **Export to Atlos**:

| Field | Default | Notes |
|-------|---------|--------|
| Base URL | `http://atlos:4000` | In-container hostname on `groupint-net` |
| API token | from env | Editable in UI |

**Presets:**

- **Local Docker** — `http://atlos:4000`
- **Cloud** — `https://platform.atlos.org`
- **Custom** — your instance URL

**Buttons:**

| Button | Action |
|--------|--------|
| Save Atlos settings | Persist URL/token to Neo4j `IncidentMonitorConfig` |
| Reset to .env defaults | Clear saved overrides |
| Test Atlos connection | HTTP check against Atlos API |
| Export filtered incidents to Atlos | POST incidents matching current map filters |

Resolution order: Neo4j saved values → `.env` / `secrets.toml` `[atlos]`.

## Export behavior

- Uses the same date/category filters as the incident map.
- `POST /api/v2/incidents/new` with description, geolocation, tags, optional source URLs.
- Sets `atlos_slug` on `Incident` nodes that exported successfully — skips re-export on next run.
- Errors shown in an expander per failed row.

Code: `core/incidents/atlos_export.py`, UI in `pages/2_Incidents.py`.

## Environment variables

```bash
ATLOS_BASE_URL=http://atlos:4000
ATLOS_API_TOKEN=your_token
```

For host-only Groupint without Docker network, use `http://localhost:13000` if Atlos publishes port 13000.

## Next steps

- [Incidents overview](overview.md)
- [Troubleshooting](../troubleshooting.md) — connection and token errors

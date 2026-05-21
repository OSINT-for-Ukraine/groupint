# Configuration

Groupint reads settings from **environment variables** (`.env`, Docker compose) and optionally **`.streamlit/secrets.toml`**.

## Environment variables (`.env`)

| Variable | Default | Used by |
|----------|---------|---------|
| `APP_NAME` | `groupint` | Docker compose project name |
| `NEO4J_URI` | `bolt://groupint-neo4j:7687` | App, worker (in Docker) |
| `NEO4J_USERNAME` | `neo4j` | App (if auth enabled) |
| `NEO4J_PASSWORD` | (see `.env.example`) | App (if auth enabled) |
| `TELEGRAM_PHONE` | — | Worker, optional UI default |
| `TELEGRAM_API_ID` | — | Worker, optional UI default |
| `TELEGRAM_API_HASH` | — | Worker, optional UI default |
| `INCIDENT_LLM_PROVIDER` | `anthropic` | Incident worker / pipeline |
| `ANTHROPIC_API_KEY` | — | When provider is `anthropic` |
| `OPENAI_API_KEY` | — | When provider is `openai` |
| `GOOGLE_MAPS_API_KEY` | — | Geocoding (optional) |
| `INCIDENT_POLL_INTERVAL_SEC` | `300` | Worker fallback if Neo4j scheduler unset |
| `ATLOS_BASE_URL` | `http://atlos:4000` | Atlos export (Docker internal hostname) |
| `ATLOS_API_TOKEN` | — | Atlos export |
| `ATLOS_DB_*` | — | Atlos compose only (`docker-compose.atlos.yml`) |

Copy from [`.env.example`](../.env.example) in the repository root.

## Streamlit secrets (`.streamlit/secrets.toml`)

### `[telegram]`

| Key | Description |
|-----|-------------|
| `phone` | Default phone for UI |
| `api_id` | Telegram application id |
| `api_hash` | Telegram application hash |

### `[incidents]` (optional)

| Key | Description |
|-----|-------------|
| `llm_provider` | `anthropic` or `openai` |
| `llm_model` | Model name override |
| `anthropic_api_key` | API key |
| `openai_api_key` | API key |
| `google_maps_api_key` | Geocoding |
| `poll_interval_sec` | Legacy poll interval |

The worker calls `apply_incidents_secrets()` to merge secrets with environment variables.

### `[atlos]` (optional)

| Key | Description |
|-----|-------------|
| `base_url` | Atlos platform URL |
| `api_token` | API token with write permission |

UI settings saved in Neo4j override env/secrets for export. See [Atlos export](incidents/atlos-export.md).

## Neo4j scheduler (Incidents UI)

These are stored in Neo4j on `IncidentMonitorConfig`, not in `.env`:

| Field | Meaning |
|-------|---------|
| `scheduler_enabled` | Auto-fetch watchlist |
| `fetch_interval_sec` | Minimum seconds between fetches |
| `run_pipeline_after_fetch` | Run LLM pipeline after ingest |
| `global_keywords` | Comma/newline-separated list |
| `global_keywords_enabled` | Apply global filter |
| `atlos_base_url` | Saved Atlos URL |
| `atlos_api_token` | Saved Atlos token |

See [Keywords and scheduler](incidents/keywords-and-scheduler.md).

## Session files

Telegram StringSessions are stored under `GROUPINT_SESSIONS_DIR` (Docker: `/home/appuser/.groupint/sessions/`). See [Sessions and authentication](telegram/sessions-and-auth.md).

## Security

- Never commit `.env`, `.streamlit/secrets.toml`, or `*.session` files.
- Rotate API tokens if exposed.
- Use separate Telegram accounts for research vs personal use when possible.

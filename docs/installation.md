# Installation

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Docker** | Recommended for production-like use; Docker Desktop for `scripts/up-desktop.sh` |
| **Python 3.11** | For local dev without Docker |
| **Poetry** | Dependency management (`pyproject.toml`) |
| **pre-commit** | Optional; linters and formatters on commit |

## Clone the repository

```bash
git clone https://github.com/OSINT-for-Ukraine/groupint.git
cd groupint
```

## Environment configuration

### `.env` (Docker and worker)

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Required for Telegram scraping:

- `TELEGRAM_PHONE` — international format, e.g. `+1234567890`
- `TELEGRAM_API_ID` — from [my.telegram.org/apps](https://my.telegram.org/apps)
- `TELEGRAM_API_HASH`

Required for the incident LLM pipeline (optional if you only use the main scraper):

- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` (see `INCIDENT_LLM_PROVIDER`)
- `GOOGLE_MAPS_API_KEY` — optional; Nominatim used as fallback for geocoding

See [Configuration](configuration.md) for the full variable list.

### `.streamlit/secrets.toml` (Streamlit defaults)

Create `.streamlit/secrets.toml` in the project root (do **not** commit to git):

```toml
[telegram]
phone = "+1234567890"
api_id = "12345678"
api_hash = "your_api_hash_here"
```

The main UI pre-fills these fields. The incident worker can use the same values via `.env` or shared Docker volumes.

Optional `[incidents]` and `[atlos]` sections are documented in [Configuration](configuration.md).

## Run with Docker (recommended)

**Groupint only:**

```bash
chmod +x scripts/up-desktop.sh
./scripts/up-desktop.sh
```

Open http://localhost:18501

**Groupint + local Atlos** (for incident export):

```bash
chmod +x scripts/up-full.sh
./scripts/up-full.sh
```

See [Docker: desktop stack](docker/desktop-stack.md) and [Docker: full stack with Atlos](docker/full-stack-with-atlos.md).

## Run locally without Docker

```bash
poetry install
poetry run streamlit run interface.py
```

Default URL: http://localhost:8501 (unless you configure another port).

You need a running Neo4j instance and matching `NEO4J_URI` / credentials in `.env`.

## Telegram API credentials

Before first use, obtain **api_id** and **api_hash** for your phone number. See [Credentials and API keys](telegram/credentials-and-api.md).

## Verify the installation

```bash
docker ps --filter name=groupint
curl -sf http://localhost:18501/_stcore/health
```

Then connect Telegram in the UI: [Sessions and authentication](telegram/sessions-and-auth.md).

## Next steps

- [Main application](main-application.md) — scrape your first group
- [Troubleshooting](troubleshooting.md) — if ports or auth fail

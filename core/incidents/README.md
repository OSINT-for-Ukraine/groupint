# Incident mapping pipeline

Pipeline design adapted from [Telegram-OSINT-Incident-Mapping](https://github.com/Namithnp/Telegram-OSINT-Incident-Mapping) (MIT).

Groupint uses Telethon + Neo4j instead of Pyrogram + SQLite, and Anthropic/OpenAI instead of Google ADK/Gemini.

## Environment

| Variable | Purpose |
|----------|---------|
| `INCIDENT_LLM_PROVIDER` | `anthropic` or `openai` |
| `INCIDENT_LLM_MODEL` | Model id |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | LLM |
| `GOOGLE_MAPS_API_KEY` | Optional geocoding (Nominatim fallback) |
| `INCIDENT_POLL_INTERVAL_SEC` | Worker interval (default 300) |
| `TELEGRAM_PHONE`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` | Worker Telegram session |

Or `[incidents]` section in `.streamlit/secrets.toml`.

## Run worker

```bash
python scripts/incident-worker.py
```

Or Docker: `groupint-incident-worker` service in `docker-compose.desktop.yml`.

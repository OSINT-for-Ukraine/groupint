# Development

Guide for contributors working on Groupint source code.

## Local setup

```bash
git clone https://github.com/OSINT-for-Ukraine/groupint.git
cd groupint
poetry install
```

Python **3.11** is required (`pyproject.toml`).

## Pre-commit

```bash
pip install pre-commit
pre-commit install
```

On commit, linters and formatters run automatically. Fix reported issues before pushing.

## Run Streamlit locally

```bash
poetry run streamlit run interface.py
```

Ensure Neo4j is reachable and `NEO4J_URI` is set in `.env`.

## Tests

```bash
poetry run pytest
```

Example incident tests: `tests/test_atlos_export.py`, `tests/test_watchlist_channels.py`.

## Docker during development

Rebuild after code changes:

```bash
./scripts/up-desktop.sh --build
# or
docker restart groupint-streamlit
```

## Project layout (selected)

| Path | Purpose |
|------|---------|
| `interface.py` | Main Streamlit app |
| `pages/2_Incidents.py` | Incidents UI |
| `core/tg_api_connector.py` | Telethon operations |
| `core/telegram_session.py` | StringSession persistence |
| `core/incidents/` | Incident pipeline |
| `db/dal.py`, `db/queries.py` | Neo4j access |
| `draw_graph/` | Plotly graph builders |
| `scripts/incident-worker.py` | Background worker |
| `docker-compose.desktop.yml` | Desktop stack |

## Contributing

1. Create a branch named for your change.
2. Make focused commits with clear messages.
3. Ensure pre-commit passes.
4. Push and open a PR to `main`.
5. Wait for CI and review.

Do not commit `.env`, `secrets.toml`, session files, or API keys.

## Internal knowledge base

Maintainer notes: `llm-wiki-vault/wiki/` (Obsidian-style). Public user docs: [`docs/index.md`](index.md).

## Related

- [Configuration](configuration.md)
- [Troubleshooting](troubleshooting.md)

# Keywords and scheduler

Control **which messages** enter the incident pipeline and **when** the worker fetches new posts from watchlisted channels.

Settings are stored in Neo4j (`IncidentMonitorConfig` and per-channel `WatchlistChannel`), not only in `.env`.

## Global keyword filter

Section: **Global keyword filter** on the Incidents page.

| Setting | Behavior |
|---------|----------|
| Global keyword list | Comma- or newline-separated terms |
| Enable global keywords | When on, messages must match at least one term (OR within list) |

Click **Save global keywords** to persist to `IncidentMonitorConfig`.

Implementation: `core/incidents/keywords.py` — `effective_keywords()`, stage `keyword_prefilter` in `core/incidents/keyword_prefilter.py`.

## Per-channel keywords

In each channel expander:

| Setting | Behavior |
|---------|----------|
| Channel keywords | Local list for that channel |
| Enable channel keywords | Apply channel list |
| **Also use global keywords** | Merge global + channel lists |

If **use global keywords** is off, only the channel list applies (when enabled).

## Effective keyword set

| Global enabled | Channel enabled | use_global | Result |
|----------------|-----------------|------------|--------|
| yes | yes | yes | Union of both lists |
| yes | yes | no | Channel list only |
| yes | no | — | Global only |
| no | yes | — | Channel only |
| no | no | — | **No filter** — all messages pass prefilter |

Matching is case-insensitive substring search on message text.

## Message fetch scheduler

Section: **Message fetch scheduler**.

| Field | Meaning |
|-------|---------|
| **Enable scheduler** | Worker auto-fetches when true |
| **Fetch interval** | Minimum seconds between runs (e.g. 1800 = 30 min) |
| **Run pipeline after fetch** | Worker runs LLM pipeline immediately after ingest |

Click **Save scheduler**.

Worker reads config each loop from Neo4j. Fallback: `INCIDENT_POLL_INTERVAL_SEC` in `.env` if Neo4j config is missing.

## Manual actions

| Button | Effect |
|--------|--------|
| **Fetch watchlist now** | Immediate poll (uses UI Telegram session) |
| **Run pipeline now** | Process queued messages through LLM stages |

## Worker behavior

Container: `groupint-incident-worker`

```bash
docker logs -f groupint-incident-worker
```

Typical loop:

1. Read scheduler config
2. If interval elapsed and scheduler enabled → `poll_all_watchlist`
3. Update `last_fetch_at`
4. If `run_pipeline_after_fetch` → run pipeline batch
5. Sleep until next check

Without LLM keys, fetch still works; pipeline LLM steps are skipped.

## Next steps

- [Incidents overview](overview.md)
- [Atlos export](atlos-export.md)

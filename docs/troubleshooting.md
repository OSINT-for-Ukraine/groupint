# Troubleshooting

Common issues when running Groupint locally or in Docker.

## Docker and ports

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| http://localhost:18501 unreachable | Containers not running | `docker ps --filter name=groupint`; run `./scripts/up-desktop.sh` |
| Port already in use | Old container or another app | `docker compose -f docker-compose.desktop.yml down`; free port 18501 |
| Wrong Neo4j port in Gephi | Legacy vs desktop stack | Desktop Bolt: **17687**; legacy: **7687** |
| `desktop-linux` context fails | System Docker vs Desktop | `docker context use default` or install Docker Desktop |

Health check:

```bash
curl -sf http://localhost:18501/_stcore/health
```

## Telegram authentication

| Symptom | Fix |
|---------|-----|
| OTP never arrives | Same phone as Telegram app; virtual number still active on SMS provider |
| Session lost on refresh | Check `.string` files in session dir; see [Sessions](telegram/sessions-and-auth.md) |
| `SessionInUseError` | One tab per phone; Disconnect in other tab |
| `secrets.toml` not loaded | File at repo root `.streamlit/secrets.toml`; restart `groupint-streamlit` |
| Channel private / not found | Account must have access; try @username or invite link |

## Neo4j

| Symptom | Fix |
|---------|-----|
| Connection refused from app | Ensure `groupint-neo4j` healthy; `NEO4J_URI=bolt://groupint-neo4j:7687` in Docker |
| Gephi Verify failed | Use `bolt://localhost:17687`, **No authentication** |
| Empty graph after scrape | Run Cypher: `MATCH (g:Group) RETURN g` — confirm canonical `g.id` |

## Scraping and graphs

| Symptom | Fix |
|---------|-----|
| `ValueError` unpack on fetch | Update to latest code; fetch returns 2/3 or 3/4 tuple variants |
| 0 messages for endorsements | Fetch messages first; confirm same canonical `Group.id` |
| Huge member list warning | Telegram `participants_count` vs dedupe limits — reduce scope |
| UI code changes not visible | `docker restart groupint-streamlit` or rebuild compose |

## Incidents worker

| Symptom | Fix |
|---------|-----|
| Scheduler not fetching | Enable scheduler in UI; check `docker logs groupint-incident-worker` |
| No incidents on map | Run pipeline; set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` |
| All messages filtered out | Review global/channel keywords; empty list = no filter |
| Manual fetch works, scheduler does not | Worker needs `TELEGRAM_*` in `.env` or shared session |

## Atlos export

| Symptom | Fix |
|---------|-----|
| Test connection failed | `up-full.sh` running; token valid; URL `http://atlos:4000` inside Docker |
| 401 / 403 on export | Token needs write permission on correct project |
| Incidents skipped | Already have `atlos_slug`; or missing lat/lon from geocode |

## Logs

```bash
docker logs -f groupint-streamlit
docker logs -f groupint-incident-worker
docker logs -f groupint-neo4j
```

## Still stuck?

Open an issue on [GitHub](https://github.com/OSINT-for-Ukraine/groupint/issues) with logs, compose file used, and steps to reproduce (redact secrets).

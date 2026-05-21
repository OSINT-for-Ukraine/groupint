# Watchlist and bulk import

The Incidents page maintains a **watchlist** of Telegram channels to poll for new messages.

## Add a single channel

1. Open **Incidents** in Streamlit.
2. Under **Watchlist channels**, enter a channel reference:
   - `@channelname`
   - `https://t.me/channelname`
   - Numeric id or invite link (as supported by Telethon)
3. Click **Add to watchlist**.

Each entry is stored as a `WatchlistChannel` node in Neo4j with `enabled = true` by default.

## Bulk import (paste or upload)

Expand **Add multiple channels (paste or upload)**.

Supported inputs:

| Format | Example |
|--------|---------|
| Plain text | One channel per line |
| CSV | Column with refs or header row |
| JSON | Array of strings or objects with `channel_ref` / `ref` |

Implementation: `core/incidents/watchlist_channels.py` — `parse_watchlist_bulk()`.

1. Paste into the text area **or** upload `.txt`, `.csv`, `.json`.
2. Review the parsed count in the UI.
3. Click **Add all to watchlist**.

Duplicates are skipped or updated according to Neo4j merge logic in the DAL.

## Per-channel settings

Each watchlist entry has an expander with:

| Control | Effect |
|---------|--------|
| **Enabled** | Include in fetch when checked |
| **Keywords** | Channel-specific filter list |
| **Use global keywords** | Combine with global list (see [keywords doc](keywords-and-scheduler.md)) |
| **Save channel** | Persist changes |
| **Remove** | Delete from watchlist |

## Fetch behavior

- **Fetch watchlist now** — manual poll using your Streamlit Telegram session (must be authorized on this page).
- **Scheduler** — background worker polls on an interval when enabled.

Fetched messages are stored as `Message` nodes linked to channel `Group` nodes, then eligible for the LLM pipeline.

## Tips

- Start with a small watchlist to validate keywords and LLM quality.
- Public channels resolve more reliably than private ones your account cannot access.
- Check worker logs if manual fetch works but scheduled fetch does not.

## Next steps

- [Keywords and scheduler](keywords-and-scheduler.md)
- [Incidents overview](overview.md)

# Main application

The default Streamlit app (`interface.py`) is for investigating a **single Telegram group** at a time: scrape members and messages into Neo4j, extract authors and cross-group links, and visualize networks.

## Before you start

- [Installation](installation.md) complete
- [Telegram session](telegram/sessions-and-auth.md) connected

Open http://localhost:18501 (desktop Docker stack).

## Target group

Enter a reference in **Target group**:

- `@public_username`
- `https://t.me/groupname`
- Group title (less reliable)

After Telethon resolves the chat, Neo4j uses a **canonical id**:

| Chat type | `Group.id` in Neo4j |
|-----------|---------------------|
| Public @username | Normalized username, e.g. `Example_Group` |
| Private / no username | `peer:{telethon_id}` |

The UI shows the canonical id after scraping. Related fields: `title`, `username`, `telegram_peer_id`, `telegram_url`, `aliases`.

## Scrape members

**Get users list** — fetches participants via `iter_participants`, saves `User` nodes and `MEMBER_OF` relationships to the `Group` node.

Progress is shown in the UI. Large groups may take several minutes.

## Messages (two-step pipeline)

| Step | Button | What it does |
|------|--------|----------------|
| 1 | **Get messages from group** | Fetches new messages from Telegram; stores `Message` nodes with `users_processed = false` |
| 2 | **Extract users from stored messages** | Reads unprocessed messages from Neo4j; resolves authors via Telegram; marks messages processed |

Optional: **Extract endorsements from messages** — finds `t.me/...` and `@username` links in stored text; creates `ENDORSES` relationships between `Group` nodes.

Caption under the buttons shows total stored messages and unprocessed counts.

### Incremental behavior

- Message fetch skips IDs already in Neo4j; stops after `limit` **new** messages.
- Re-fetching an existing message does not reset `users_processed`.
- User extract can add id-only rows if Telegram does not return full profile — batch does not abort.

## Previously scraped groups

Dropdown populated from `GraphManager.list_scraped_groups()` — pick a past target to pre-fill the group field.

## Manage Neo4j data

Expand **Manage Neo4j data**:

- **Merge duplicate groups** — clusters legacy duplicates by `telegram_peer_id`, URL, or username
- **Delete** one group’s data from Neo4j

One-time shell helper: `scripts/merge-duplicate-groups.sh`

## Graphs in Streamlit

After data is in Neo4j:

| Action | Graph type |
|--------|------------|
| **Show graph** | Member network for the target group (static / interactive) |
| **Graph by common groups** | `RELATED` edges between users who share groups |
| **Graph by endorsements** | `ENDORSES` between groups (limit N, default 200) |

For large graphs or publication layouts, use [Neo4j and Gephi](neo4j-and-gephi.md).

## Neo4j Browser link

The UI may link to Neo4j Browser (desktop stack: http://localhost:17474) for ad-hoc Cypher.

Example check:

```bash
docker exec groupint-neo4j cypher-shell -a bolt://localhost:7687 \
  "MATCH (g:Group) RETURN g.id, g.title, g.user_counts LIMIT 10"
```

## Upload alternative data

You can upload **JSON** or **XLS** user lists instead of live Telegram member scrape (`core/upload_file.py`). `scrape_source` on the group reflects `file_json` or `file_xlsx`.

## Incidents tab

For channel monitoring and geocoded incident maps, switch to the **Incidents** page in the sidebar. See [Incidents overview](incidents/overview.md).

## Next steps

- [Neo4j and Gephi](neo4j-and-gephi.md)
- [Troubleshooting](troubleshooting.md)

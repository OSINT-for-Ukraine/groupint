query_hint = """
**Scraped groups** appear in the dropdown after you extract members (**Get users list**). All scrapes are saved to Neo4j under a **canonical group id** (public @username, or `peer:123…` for private chats)—the target group field can be a title, @name, or t.me link. Use **Manage Neo4j data** to merge duplicate groups or delete one group's graph data.

**Telegram sessions** (sidebar): saved StringSessions reconnect on page reload without OTP when still valid.

**Messages (3 steps):**
1. **Get messages from group** — stores message text in Neo4j (deduped by message id); each `Message` has `telegram_url`
2. **Extract users from stored messages** — only unprocessed messages; `User.telegram_url` set when known
3. **Extract endorsements from messages** — t.me / @username links → `ENDORSES` edges between `Group` nodes

**Graphs from Neo4j** (main area):
- **Graph by common groups** — builds `RELATED` edges (users sharing scraped groups), then plots the user graph
- **Graph by endorsements** — plots `Group`→`Group` via `ENDORSES` (run step 3 first)

**Fetch graph from storage** / **On server** → Neo4j Browser:

With integer N:
- *N — User nodes, limit N
- intersection_more_than_N — pairs in > N shared groups
- more_than_N_groups — users in > N groups
- endorsement_graph — directed Group→Group via ENDORSES (default N=200 if empty)
- common_groups_graph — RELATED user pairs (default N=200 if empty)

Without integer:
- the_most_groups_per_user
- size_rating_for_groups
- db_labels — list labels in the database

Neo4j Browser: http://localhost:17474 — auth **No authentication**, Connect once.

**Gephi (Neo4j plugin):** URL `neo4j://localhost:17687`, **No authentication**, Verify on step 1. Label lists use `CALL db.labels()` (first wizard tab), not the default `MATCH (n) RETURN id, labels` test query. See `docs/neo4j-and-gephi.md` in the repository.
"""

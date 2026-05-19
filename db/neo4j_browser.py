"""Build Neo4j Browser URLs with a pre-filled Cypher query."""

import os
import re
from urllib.parse import urlencode

from db.queries import query_dict

_WRITE_QUERY_KEYS = frozenset(
    {
        "creator_query",
        "add_user",
        "add_groups_to_user",
        "create_relationship_between_users_of_same_groups",
        "persist_group_members",
    }
)


def _compact_cypher(cypher: str) -> str:
    return re.sub(r"\s+", " ", cypher.strip())


def cypher_for_browser(query_key: str, n: int | None = None) -> str:
    """Return a single-line Cypher string for Neo4j Browser (parameters inlined)."""
    if query_key in _WRITE_QUERY_KEYS:
        raise ValueError(
            f"{query_key!r} is a write query and cannot be opened as a graph view."
        )
    cypher = query_dict.get(query_key)
    if cypher is None:
        known = ", ".join(sorted(k for k in query_dict if k not in _WRITE_QUERY_KEYS))
        raise ValueError(f"Unknown graph query {query_key!r}. Try: {known}")
    cypher = _compact_cypher(cypher)
    if "$N" in cypher:
        if n is None:
            raise ValueError(f"Query {query_key!r} requires an integer argument (N).")
        cypher = cypher.replace("$N", str(n))
    return cypher


def neo4j_browser_url(query_key: str, n: int | None = None) -> str:
    """
    Neo4j Browser deep link for Docker Desktop (NEO4J_AUTH=none).

    Uses dbms + preselectAuthMethod=NO_AUTH so the UI shows "No authentication"
    instead of username/password. You still click **Connect** once per browser;
    the browser then remembers localhost:17687 for later visits.

    Env (host browser):
      NEO4J_BROWSER_URL — http://localhost:17474/browser/
      NEO4J_BROWSER_CONNECT_URL — bolt://localhost:17687
      NEO4J_BROWSER_DATABASE — neo4j
      NEO4J_BROWSER_AUTH_METHOD — NO_AUTH (default)
    """
    cypher = cypher_for_browser(query_key, n)
    browser_base = os.environ.get(
        "NEO4J_BROWSER_URL", "http://localhost:17474/browser/"
    ).rstrip("/")
    connect_url = os.environ.get(
        "NEO4J_BROWSER_CONNECT_URL", "bolt://localhost:17687"
    )
    database = os.environ.get("NEO4J_BROWSER_DATABASE", "neo4j")
    auth_method = os.environ.get("NEO4J_BROWSER_AUTH_METHOD", "NO_AUTH")
    params = {
        "dbms": connect_url,
        "db": database,
        "preselectAuthMethod": auth_method,
        "cmd": "edit",
        "arg": cypher,
    }
    return f"{browser_base}/?{urlencode(params)}"

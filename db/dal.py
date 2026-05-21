from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Type, Union

from py2neo import Node
from py2neo.integration import Table

from core.group_identity import pick_winner_group_id
from core.telegram_urls import group_url, user_url
from db.config import graph
from db.queries import query_dict
from models import FetchedChannel

if TYPE_CHECKING:
    from core.group_identity import ResolvedGroup


def _scraped_group_cluster_key(row: dict) -> str | None:
    peer = row.get("telegram_peer_id")
    if peer is not None:
        return f"peer:{int(peer)}"
    url = (row.get("telegram_url") or "").strip().lower()
    if url:
        return f"url:{url}"
    username = (row.get("username") or "").strip().lower()
    if username:
        return f"user:{username}"
    gid = (row.get("id") or "").strip()
    if gid:
        return f"id:{gid}"
    return None


def dedupe_scraped_groups(rows: list[dict]) -> list[dict]:
    """One row per real chat; cluster by peer id, url, or username when present."""
    clusters: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = _scraped_group_cluster_key(row)
        if key is None:
            continue
        clusters[key].append(row)

    merged: list[dict] = []
    for cluster in clusters.values():
        ids = [(r.get("id") or "").strip() for r in cluster if (r.get("id") or "").strip()]
        winner_id = pick_winner_group_id(ids) if ids else ""
        best: dict | None = None
        for row in cluster:
            row_id = (row.get("id") or "").strip()
            if row_id == winner_id or best is None:
                if best is None or (row.get("scraped_at") or "") >= (
                    best.get("scraped_at") or ""
                ):
                    best = dict(row)
        if best is None:
            continue
        best["id"] = winner_id or best.get("id")
        members = max(
            (int(r.get("members") or 0) for r in cluster),
            default=int(best.get("members") or 0),
        )
        best["members"] = members
        merged.append(best)
    return merged


class GraphManager:

    @staticmethod
    def add_user(user: tuple, groups: list) -> None:
        parameters = {
            "user_id": user[0],
            "username": user[1],
            "alias": user[2],
            "groups": groups,
        }
        graph.run(query_dict.get("add_user"), parameters)

    @staticmethod
    def create_relationships() -> None:
        graph.run(query_dict.get("create_relationship_between_users_of_same_groups"))

    @staticmethod
    def list_scraped_groups() -> list[dict]:
        """All Group nodes saved from prior scrapes, newest first."""
        try:
            rows = graph.run(query_dict["list_scraped_groups"]).data()
        except Exception:
            return []
        return dedupe_scraped_groups(rows)

    @staticmethod
    def _group_persist_params(
        group_ref: str,
        *,
        group_title: str | None = None,
        group_meta: "ResolvedGroup | None" = None,
    ) -> dict:
        title = group_title or group_ref
        username = None
        peer_id = None
        aliases: list[str] = []
        telegram_url = group_url(group_ref)
        if group_meta is not None:
            title = group_meta.title or title
            username = group_meta.username
            peer_id = group_meta.telegram_peer_id
            aliases = list(group_meta.aliases or [])
            if group_meta.telegram_url:
                telegram_url = group_meta.telegram_url
        return {
            "group_title": title,
            "group_username": username,
            "telegram_peer_id": peer_id,
            "aliases": aliases,
            "group_telegram_url": telegram_url,
        }

    @staticmethod
    def add_extracted_group_members(
        group_ref: str,
        users: list[tuple],
        *,
        group_title: str | None = None,
        scrape_source: str = "members",
        group_meta: "ResolvedGroup | None" = None,
    ) -> int:
        """Write Telegram member list into Neo4j (User + Group + MEMBER_OF)."""
        if not users:
            return 0
        by_id: dict[int, dict] = {}
        for user in users:
            if not user or user[0] is None:
                continue
            uid = int(user[0])
            username = (user[1] or "") if len(user) > 1 else ""
            alias = (user[2] or "") if len(user) > 2 else ""
            if uid in by_id:
                if username:
                    by_id[uid]["username"] = username
                    by_id[uid]["telegram_url"] = user_url(uid, username)
                if alias:
                    by_id[uid]["alias"] = alias
            else:
                by_id[uid] = {
                    "id": uid,
                    "username": username,
                    "alias": alias,
                    "telegram_url": user_url(uid, username or None),
                }
        payload = list(by_id.values())
        if not payload:
            return 0
        meta = GraphManager._group_persist_params(
            group_ref, group_title=group_title, group_meta=group_meta
        )
        rows = graph.run(
            query_dict["persist_group_members"],
            {
                "group_id": group_ref,
                "users": payload,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "scrape_source": scrape_source,
                **meta,
            },
        ).data()
        if rows and rows[0].get("member_count") is not None:
            return int(rows[0]["member_count"])
        return len(payload)

    @staticmethod
    def persist_group_messages(
        group_ref: str,
        messages: list[dict],
        *,
        group_meta: "ResolvedGroup | None" = None,
    ) -> int:
        """Insert new Message nodes; existing ids are not re-created."""
        if not messages:
            return 0
        meta = GraphManager._group_persist_params(group_ref, group_meta=group_meta)
        rows = graph.run(
            query_dict["persist_group_messages"],
            {
                "group_id": group_ref,
                "messages": messages,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                **meta,
            },
        ).data()
        if not rows:
            return 0
        inserted = rows[0].get("inserted")
        return int(inserted) if inserted is not None else 0

    @staticmethod
    def stored_message_ids(group_ref: str) -> set[int]:
        try:
            rows = graph.run(
                query_dict["list_stored_message_ids"], {"group_id": group_ref}
            ).data()
        except Exception:
            return set()
        return {
            int(row["message_id"])
            for row in rows
            if row.get("message_id") is not None
        }

    @staticmethod
    def lookup_users_by_ids(user_ids: list[int]) -> dict[int, tuple[int, str | None, str]]:
        if not user_ids:
            return {}
        rows = graph.run(
            query_dict["lookup_users_by_ids"],
            {"user_ids": [int(uid) for uid in user_ids]},
        ).data()
        result: dict[int, tuple[int, str | None, str]] = {}
        for row in rows:
            uid = row.get("id")
            if uid is None:
                continue
            result[int(uid)] = (
                int(uid),
                row.get("username") or None,
                row.get("alias") or "",
            )
        return result

    @staticmethod
    def min_stored_message_id(group_ref: str) -> int | None:
        rows = graph.run(
            query_dict["min_stored_message_id"], {"group_id": group_ref}
        ).data()
        if not rows or rows[0].get("min_id") is None:
            return None
        return int(rows[0]["min_id"])

    @staticmethod
    def count_group_messages(group_ref: str) -> dict[str, int]:
        rows = graph.run(
            query_dict["count_group_messages"], {"group_id": group_ref}
        ).data()
        if not rows:
            return {"total": 0, "unprocessed": 0, "links_unprocessed": 0}
        return {
            "total": int(rows[0].get("total") or 0),
            "unprocessed": int(rows[0].get("unprocessed") or 0),
            "links_unprocessed": int(rows[0].get("links_unprocessed") or 0),
        }

    @staticmethod
    def list_unprocessed_messages_for_links(group_ref: str) -> list[dict]:
        rows = graph.run(
            query_dict["unprocessed_messages_for_links"], {"group_id": group_ref}
        ).data()
        return [
            {
                "message_id": int(row["message_id"]),
                "text": row.get("text") or "",
                "date": row.get("date"),
            }
            for row in rows
            if row.get("message_id") is not None
        ]

    @staticmethod
    def persist_endorsements(source_id: str, links: list[dict]) -> int:
        if not links:
            return 0
        rows = graph.run(
            query_dict["persist_endorsements"],
            {
                "source_id": source_id,
                "source_telegram_url": group_url(source_id),
                "links": links,
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            },
        ).data()
        if not rows:
            return 0
        return int(rows[0].get("inserted") or 0)

    @staticmethod
    def mark_messages_links_processed(group_ref: str) -> int:
        rows = graph.run(
            query_dict["mark_messages_links_processed"], {"group_id": group_ref}
        ).data()
        if not rows:
            return 0
        return int(rows[0].get("marked") or 0)

    @staticmethod
    def list_unprocessed_author_ids(group_ref: str) -> list[int]:
        rows = graph.run(
            query_dict["unprocessed_message_authors"], {"group_id": group_ref}
        ).data()
        return [int(row["author_id"]) for row in rows if row.get("author_id") is not None]

    @staticmethod
    def list_unprocessed_messages_for_users(group_ref: str) -> list[dict]:
        rows = graph.run(
            query_dict["unprocessed_messages_for_users"], {"group_id": group_ref}
        ).data()
        return [
            {
                "message_id": int(row["message_id"]),
                "from_user_id": int(row["from_user_id"]),
            }
            for row in rows
            if row.get("message_id") is not None and row.get("from_user_id") is not None
        ]

    @staticmethod
    def delete_group_data(group_id: str) -> int:
        """Remove all Group nodes with this id, plus messages, memberships, and endorsements.

        Returns the number of Group nodes deleted (0 if none matched).
        """
        ref = (group_id or "").strip()
        if not ref:
            return 0
        try:
            before = graph.run(
                "MATCH (g:Group) WHERE g.id = $group_id RETURN count(g) AS c",
                {"group_id": ref},
            ).data()
            expected = int(before[0]["c"]) if before else 0
            if expected == 0:
                return 0
            rows = graph.run(
                query_dict["delete_group_data"], {"group_id": ref}
            ).data()
            if not rows or not rows[0].get("deleted_id"):
                return 0
            after = graph.run(
                "MATCH (g:Group) WHERE g.id = $group_id RETURN count(g) AS c",
                {"group_id": ref},
            ).data()
            remaining = int(after[0]["c"]) if after else 0
            return max(expected - remaining, 0)
        except Exception:
            return 0

    @staticmethod
    def mark_group_messages_processed(group_ref: str) -> int:
        rows = graph.run(
            query_dict["mark_messages_processed"], {"group_id": group_ref}
        ).data()
        if not rows:
            return 0
        return int(rows[0].get("marked") or 0)

    @staticmethod
    def import_json_users(json_data: dict) -> dict[str, int]:
        """Import Telesint-style JSON: each user has a list of group @names."""
        from collections import defaultdict

        from core.tg_api_connector import normalize_telegram_group_ref

        groups_users: dict[str, list[tuple]] = defaultdict(list)
        for user in json_data.values():
            if not isinstance(user, dict):
                continue
            user_id = user.get("id")
            if user_id is None:
                continue
            username = user.get("username") or ""
            groups = user.get("groups")
            if not groups:
                continue
            row = (int(user_id), username, username)
            for group_name in groups:
                ref = normalize_telegram_group_ref(str(group_name))
                if ref:
                    groups_users[ref].append(row)

        saved_by_group: dict[str, int] = {}
        for ref, members in groups_users.items():
            saved_by_group[ref] = GraphManager.add_extracted_group_members(
                ref,
                members,
                group_title=ref,
                scrape_source="file_json",
            )
        return saved_by_group

    @staticmethod
    def add_fetched_channel(instance: FetchedChannel) -> None:
        group_map = instance.model_dump()
        user_set = group_map.pop("user_set")
        group_node = Node("Group", **group_map)
        user_nodes = []
        for user in user_set:
            user_node = Node("User", id=user[0], username=user[1], first_name=user[2])
            user_nodes.append(user_node)
        parameters = {
            "group_id": group_node["id"],
            "group_properties": dict(group_node),
            "user_nodes": user_nodes,
        }
        print("Start to add data into storage")
        print(len(user_set))
        graph.run(query_dict.get("creator_query"), parameters)

    @staticmethod
    def merge_duplicate_groups(*, ensure_unique_constraint: bool = False) -> dict:
        """Merge Group nodes that share peer id, telegram_url, or username."""
        same_id_merged = 0
        try:
            rows = graph.run(query_dict["merge_same_property_group_id"]).data()
            if rows and rows[0].get("merged_nodes") is not None:
                same_id_merged = int(rows[0]["merged_nodes"])
        except Exception:
            pass

        try:
            rows = graph.run(query_dict["list_all_groups"]).data()
        except Exception:
            return {
                "clusters": 0,
                "merged": same_id_merged,
                "same_id_nodes_merged": same_id_merged,
                "errors": ["list_all_groups failed"],
            }

        clusters: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            gid = (row.get("id") or "").strip()
            if not gid:
                continue
            key = _scraped_group_cluster_key(row)
            if key is None:
                key = f"id:{gid}"
            clusters[key].append(row)

        merged_count = 0
        cluster_count = 0
        for cluster in clusters.values():
            if len(cluster) < 2:
                continue
            ids = sorted({(r.get("id") or "").strip() for r in cluster if (r.get("id") or "").strip()})
            if not ids:
                continue
            cluster_count += 1
            winner = pick_winner_group_id(ids)
            peer_id = next(
                (r.get("telegram_peer_id") for r in cluster if r.get("telegram_peer_id")),
                None,
            )
            tg_url = next(
                (r.get("telegram_url") for r in cluster if r.get("telegram_url")),
                None,
            )
            username = next(
                (r.get("username") for r in cluster if r.get("username")),
                None,
            )
            title = next((r.get("title") for r in cluster if r.get("title")), None)
            graph.run(
                """
                MATCH (g:Group {id: $winner_id})
                SET g.telegram_peer_id = coalesce(g.telegram_peer_id, $peer_id),
                    g.telegram_url = coalesce(g.telegram_url, $url),
                    g.username = coalesce(g.username, $username),
                    g.title = coalesce(g.title, $title)
                """,
                {
                    "winner_id": winner,
                    "peer_id": peer_id,
                    "url": tg_url,
                    "username": username,
                    "title": title,
                },
            )
            dup_ids = [g for g in ids if g != winner]
            alias_ids = list(dup_ids)
            for row in cluster:
                for alias in row.get("aliases") or []:
                    if alias and alias not in alias_ids and alias != winner:
                        alias_ids.append(alias)

            for dup_id in dup_ids:
                graph.run(
                    query_dict["merge_member_of_to_winner"],
                    {"dup_id": dup_id, "winner_id": winner},
                )
                graph.run(
                    query_dict["migrate_messages_dup_to_winner"],
                    {"dup_id": dup_id, "winner_id": winner},
                )
                graph.run(
                    query_dict["rewire_endorses_dup_to_winner"],
                    {"dup_id": dup_id, "winner_id": winner},
                )
                graph.run(
                    query_dict["rewrite_user_group_list"],
                    {"alias_ids": alias_ids + [dup_id], "winner_id": winner},
                )
                graph.run(query_dict["detach_delete_group"], {"group_id": dup_id})
                merged_count += 1

            graph.run(
                query_dict["recompute_group_member_count"], {"group_id": winner}
            )

        constraint_ok = False
        if ensure_unique_constraint and merged_count >= 0:
            try:
                graph.run(query_dict["ensure_group_id_unique"])
                constraint_ok = True
            except Exception:
                constraint_ok = False

        return {
            "clusters": cluster_count,
            "merged": merged_count + same_id_merged,
            "same_id_nodes_merged": same_id_merged,
            "constraint_applied": constraint_ok,
        }

    @staticmethod
    def ensure_group_id_unique_constraint() -> bool:
        try:
            graph.run(query_dict["ensure_group_id_unique"])
            return True
        except Exception:
            return False

    @staticmethod
    def ensure_incident_constraints() -> bool:
        ok = True
        for key in (
            "ensure_incident_constraints",
            "ensure_watchlist_channel_ref_unique",
            "ensure_incident_monitor_config_id",
        ):
            try:
                graph.run(query_dict[key])
            except Exception:
                ok = False
        return ok

    @staticmethod
    def list_watchlist_channels() -> list[dict]:
        try:
            return graph.run(query_dict["list_watchlist_channels"]).data()
        except Exception:
            return []

    @staticmethod
    def get_incident_monitor_config() -> dict:
        rows = graph.run(query_dict["get_incident_monitor_config"]).data()
        if not rows:
            return {}
        row = rows[0]
        return {
            "id": row.get("id", "default"),
            "global_keywords": list(row.get("global_keywords") or []),
            "global_keywords_enabled": bool(row.get("global_keywords_enabled")),
            "fetch_interval_sec": int(row.get("fetch_interval_sec") or 300),
            "scheduler_enabled": bool(row.get("scheduler_enabled")),
            "last_fetch_at": row.get("last_fetch_at"),
            "run_pipeline_after_fetch": bool(
                row.get("run_pipeline_after_fetch", True)
            ),
            "atlos_base_url": row.get("atlos_base_url"),
            "atlos_api_token": row.get("atlos_api_token"),
        }

    @staticmethod
    def upsert_incident_monitor_config(**fields: object) -> None:
        graph.run(
            query_dict["upsert_incident_monitor_config"],
            {
                "global_keywords": fields.get("global_keywords"),
                "global_keywords_enabled": fields.get("global_keywords_enabled"),
                "fetch_interval_sec": fields.get("fetch_interval_sec"),
                "scheduler_enabled": fields.get("scheduler_enabled"),
                "last_fetch_at": fields.get("last_fetch_at"),
                "run_pipeline_after_fetch": fields.get("run_pipeline_after_fetch"),
                "atlos_base_url": fields.get("atlos_base_url"),
                "atlos_api_token": fields.get("atlos_api_token"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    @staticmethod
    def set_incident_atlos_export(incident_id: str, atlos_slug: str) -> None:
        graph.run(
            query_dict["set_incident_atlos_export"],
            {
                "incident_id": incident_id,
                "atlos_slug": atlos_slug,
                "atlos_exported_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    @staticmethod
    def list_incidents_for_export(
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        category: str | None = None,
        skip_exported: bool = True,
        limit: int = 5000,
    ) -> list[dict]:
        rows = graph.run(
            query_dict["list_incidents_for_export"],
            {
                "date_from": date_from,
                "date_to": date_to,
                "category": category,
                "skip_exported": skip_exported,
                "limit": int(limit),
            },
        ).data()
        for row in rows:
            urls = row.get("source_urls") or []
            row["source_urls"] = [u for u in urls if u and str(u).strip().startswith("http")]
        return rows

    @staticmethod
    def get_watchlist_channel(channel_ref: str) -> dict | None:
        rows = graph.run(
            query_dict["get_watchlist_channel"], {"channel_ref": channel_ref}
        ).data()
        return rows[0] if rows else None

    @staticmethod
    def upsert_watchlist_channel(
        channel_ref: str,
        *,
        enabled: bool = True,
        title: str | None = None,
        last_polled_at: str | None = None,
        last_message_id: int | None = None,
        keywords: list[str] | None = None,
        keywords_enabled: bool | None = None,
        use_global_keywords: bool | None = None,
    ) -> None:
        graph.run(
            query_dict["upsert_watchlist_channel"],
            {
                "channel_ref": channel_ref,
                "enabled": enabled,
                "title": title,
                "last_polled_at": last_polled_at,
                "last_message_id": last_message_id,
                "keywords": keywords,
                "keywords_enabled": keywords_enabled,
                "use_global_keywords": use_global_keywords,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    @staticmethod
    def delete_watchlist_channel(channel_ref: str) -> None:
        graph.run(
            query_dict["delete_watchlist_channel"], {"channel_ref": channel_ref}
        )

    @staticmethod
    def messages_pending_keyword_prefilter(limit: int = 64) -> list[dict]:
        return graph.run(
            query_dict["messages_pending_keyword_prefilter"], {"limit": int(limit)}
        ).data()

    @staticmethod
    def messages_pending_clean(limit: int = 32) -> list[dict]:
        return graph.run(
            query_dict["messages_pending_clean"], {"limit": int(limit)}
        ).data()

    @staticmethod
    def messages_pending_filter(limit: int = 32) -> list[dict]:
        return graph.run(
            query_dict["messages_pending_filter"], {"limit": int(limit)}
        ).data()

    @staticmethod
    def messages_pending_dedupe(limit: int = 200) -> list[dict]:
        return graph.run(
            query_dict["messages_pending_dedupe"], {"limit": int(limit)}
        ).data()

    @staticmethod
    def messages_pending_extract(limit: int = 32) -> list[dict]:
        return graph.run(
            query_dict["messages_pending_extract"], {"limit": int(limit)}
        ).data()

    @staticmethod
    def messages_pending_geocode(limit: int = 32) -> list[dict]:
        return graph.run(
            query_dict["messages_pending_geocode"], {"limit": int(limit)}
        ).data()

    @staticmethod
    def messages_pending_incident_link(limit: int = 32) -> list[dict]:
        return graph.run(
            query_dict["messages_pending_incident_link"], {"limit": int(limit)}
        ).data()

    @staticmethod
    def messages_for_dedupe_by_date(date_prefix: str | None, limit: int = 500) -> list[dict]:
        rows = graph.run(
            query_dict["messages_for_dedupe_by_date"],
            {"date_prefix": date_prefix, "limit": int(limit)},
        ).data()
        return rows[: int(limit)]

    @staticmethod
    def update_message_incident_fields(
        group_id: str,
        message_id: int,
        **fields: object,
    ) -> None:
        params: dict = {
            "group_id": group_id,
            "message_id": int(message_id),
            "text_clean": fields.get("text_clean"),
            "incident_checked": fields.get("incident_checked"),
            "incident_processed": fields.get("incident_processed"),
            "category": fields.get("category"),
            "location_text": fields.get("location_text"),
            "lat": fields.get("lat"),
            "lon": fields.get("lon"),
            "pipeline_stage": fields.get("pipeline_stage"),
        }
        graph.run(query_dict["update_message_incident_fields"], params)

    @staticmethod
    def merge_incident_from_message(
        group_id: str,
        message_id: int,
        incident_id: str,
        *,
        category: str,
        location_text: str,
        lat: float,
        lon: float,
        occurred_at: str | None = None,
        summary: str | None = None,
        dedupe_cluster_id: str | None = None,
    ) -> str:
        rows = graph.run(
            query_dict["merge_incident_from_message"],
            {
                "group_id": group_id,
                "message_id": int(message_id),
                "incident_id": incident_id,
                "category": category,
                "location_text": location_text,
                "lat": float(lat),
                "lon": float(lon),
                "occurred_at": occurred_at,
                "summary": summary,
                "dedupe_cluster_id": dedupe_cluster_id or incident_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        ).data()
        if rows and rows[0].get("incident_id"):
            return str(rows[0]["incident_id"])
        return incident_id

    @staticmethod
    def link_message_to_incident(
        group_id: str, message_id: int, incident_id: str
    ) -> None:
        graph.run(
            query_dict["link_message_to_incident"],
            {
                "group_id": group_id,
                "message_id": int(message_id),
                "incident_id": incident_id,
            },
        )

    @staticmethod
    def incident_pipeline_counts() -> dict[str, int]:
        rows = graph.run(query_dict["incident_pipeline_counts"]).data()
        if not rows:
            return {}
        row = rows[0]
        return {k: int(row.get(k) or 0) for k in row}

    @staticmethod
    def list_incidents_for_map(
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        category: str | None = None,
        limit: int = 5000,
    ) -> list[dict]:
        return graph.run(
            query_dict["list_incidents_for_map"],
            {
                "date_from": date_from,
                "date_to": date_to,
                "category": category,
                "limit": int(limit),
            },
        ).data()

    @staticmethod
    def fetch_data(
        query_key: str, n: int = None, out_type: str = "map"
    ) -> Union[Table, dict, Type["DataFrame"]]:
        if not query_key or not str(query_key).strip():
            raise ValueError(
                "No graph query selected. Enter a query name from the sidebar hint "
                "(e.g. *N, intersection_more_than_N, size_rating_for_groups)."
            )
        query = query_dict.get(query_key.strip())
        if query is None:
            known = ", ".join(sorted(query_dict.keys()))
            raise ValueError(
                f"Unknown graph query {query_key!r}. Known queries: {known}"
            )
        raw_result = graph.run(query, parameters={"N": n})
        match out_type:
            case "table":
                result = (
                    raw_result.to_table()
                )  # вывод таблицы <class 'py2neo.integration.Table'>
            case "dframe":
                result = raw_result.to_data_frame()  # for pandas
            case "map":
                result = raw_result.data()  # вывод in dict
            case _:
                raise AttributeError("Here is no such type of output data")
        return result

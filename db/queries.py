query_dict = {
    "*N": """
        MATCH (n:User) RETURN n LIMIT $N
        """,
    #  problem here the same group update groups_count for user
    "creator_query": """
        MERGE (group:Group {id: $group_id})
        SET group += $group_properties
        WITH group
        UNWIND $user_nodes AS user_node
        MERGE (user:User {id: user_node.id})
        SET user += user_node
        SET user.groups_count = coalesce(user.groups_count, 0) + 1
        SET user.group = coalesce(user.group, []) + [$group_id] // add list of groups as a property not only as a relation, easier to parse
        MERGE (user)-[:MEMBER_OF]->(group)
        """,
    "add_user": """
        MERGE (user:User {id: $user_id})
        SET user.username = $username
        SET user.alias = $alias
        WITH user
        UNWIND $groups AS group_id
        SET user.group = coalesce(user.group, []) + [group_id]
        """,
    "add_groups_to_user": """
        MATCH (user:User)
        WHERE user.id = $user_id
        UNWIND $groups AS group_id
        SET user.group = coalesce(user.group, []) + [group_id]
        """,
    "create_relationship_between_users_of_same_groups": """
        MATCH (n1:User)
        Where size(n1.group)>1 // get rid of trivial relations when user is only part of one group
        MATCH (n2:User)
        Where size(n2.group)>1
        with n1,n2, [el in n1.group where el in n2.group] as gr 
        where size(gr)>0 and n1<>n2 // at least 1 shared groups is required to form a relation
        MERGE (n1)-[c:RELATED]-(n2)
        SET c.group=gr, c.strength=size(gr)
        return n1,n2
        """,
    "intersection_more_than_N": """
        MATCH (u1:User)-[:MEMBER_OF]->(g:Group)<-[:MEMBER_OF]-(u2:User)
        WHERE u1 <> u2
        WITH u1, u2, COLLECT(DISTINCT g) AS commonGroups
        WHERE SIZE(commonGroups) > $N
        RETURN u1, u2
        """,  # retrieve the users with more than N intersection in the same groups
    "more_than_N_groups": """
        MATCH (u:User)
        WHERE u.groups_count > $N
        RETURN *
        ORDER BY u.groups_count DESC
        """,  # retrieve the users with more than N groups
    "the_most_groups_per_user": """
        MATCH (u:User) 
        WITH MAX(u.groups_count) AS max_groups
        MATCH (u:User)
        WHERE u.groups_count = max_groups
        RETURN u
        """,  # retrieve the users with the most groups
    "size_rating_for_groups": """
        MATCH (g:Group) 
        RETURN g.id, g.title, g.user_counts 
        ORDER BY g.user_counts DESC
        """,  # retrieve a rating of the groups ordered by the size
    "persist_group_members": """
        MERGE (group:Group {id: $group_id})
        SET group.title = coalesce($group_title, group.title),
            group.last_scraped_at = $scraped_at,
            group.scrape_source = $scrape_source,
            group.telegram_url = coalesce($group_telegram_url, group.telegram_url),
            group.username = coalesce($group_username, group.username),
            group.telegram_peer_id = coalesce($telegram_peer_id, group.telegram_peer_id),
            group.aliases = CASE
                WHEN $aliases IS NULL OR size($aliases) = 0
                THEN coalesce(group.aliases, [])
                ELSE $aliases
            END
        WITH group
        UNWIND $users AS u
        MERGE (user:User {id: u.id})
        SET user.username = CASE
                WHEN u.username IS NOT NULL AND trim(u.username) <> ''
                THEN u.username
                ELSE user.username
            END,
            user.alias = CASE
                WHEN u.alias IS NOT NULL AND trim(u.alias) <> ''
                THEN u.alias
                ELSE user.alias
            END,
            user.telegram_url = CASE
                WHEN u.telegram_url IS NOT NULL AND trim(u.telegram_url) <> ''
                THEN u.telegram_url
                ELSE user.telegram_url
            END
        SET user.group = CASE
            WHEN $group_id IN coalesce(user.group, []) THEN user.group
            ELSE coalesce(user.group, []) + [$group_id]
        END
        MERGE (user)-[:MEMBER_OF]->(group)
        WITH group
        MATCH (member:User)-[:MEMBER_OF]->(group)
        WITH group, count(member) AS member_count
        SET group.user_counts = member_count
        RETURN member_count
        """,
    "list_scraped_groups": """
        MATCH (g:Group)
        RETURN g.id AS id,
               g.title AS title,
               g.user_counts AS members,
               g.last_scraped_at AS scraped_at,
               g.scrape_source AS source,
               g.telegram_peer_id AS telegram_peer_id,
               g.username AS username,
               g.telegram_url AS telegram_url
        ORDER BY g.last_scraped_at DESC
        """,
    "db_labels": """
        CALL db.labels() YIELD label
        RETURN label ORDER BY label
        """,
    "persist_group_messages": """
        MERGE (group:Group {id: $group_id})
        SET group.last_message_fetch_at = $fetched_at,
            group.telegram_url = coalesce($group_telegram_url, group.telegram_url),
            group.title = coalesce($group_title, group.title),
            group.username = coalesce($group_username, group.username),
            group.telegram_peer_id = coalesce($telegram_peer_id, group.telegram_peer_id)
        WITH group
        UNWIND $messages AS msg
        MERGE (m:Message {group_id: $group_id, message_id: msg.message_id})
        ON CREATE SET
            m.from_user_id = msg.from_user_id,
            m.date = msg.date,
            m.text = msg.text,
            m.telegram_url = msg.telegram_url,
            m.users_processed = false,
            m.links_processed = false,
            m._new = true
        ON MATCH SET
            m._new = false,
            m.from_user_id = coalesce(msg.from_user_id, m.from_user_id),
            m.date = coalesce(msg.date, m.date),
            m.text = coalesce(msg.text, m.text),
            m.telegram_url = coalesce(msg.telegram_url, m.telegram_url)
        MERGE (m)-[:IN_GROUP]->(group)
        WITH sum(CASE WHEN m._new THEN 1 ELSE 0 END) AS inserted
        RETURN inserted
        """,
    "unprocessed_messages_for_links": """
        MATCH (m:Message {group_id: $group_id})
        WHERE coalesce(m.links_processed, false) = false
          AND m.text IS NOT NULL AND trim(m.text) <> ''
        RETURN m.message_id AS message_id,
               m.text AS text,
               m.date AS date
        ORDER BY m.message_id
        """,
    "mark_messages_links_processed": """
        MATCH (m:Message {group_id: $group_id})
        WHERE coalesce(m.links_processed, false) = false
        SET m.links_processed = true
        RETURN count(m) AS marked
        """,
    "persist_endorsements": """
        MERGE (source:Group {id: $source_id})
        SET source.telegram_url = coalesce($source_telegram_url, source.telegram_url)
        WITH source
        UNWIND $links AS link
        MERGE (target:Group {id: link.target_ref})
        SET target.telegram_url = coalesce(link.target_telegram_url, target.telegram_url)
        MERGE (source)-[e:ENDORSES {message_id: link.message_id}]->(target)
        ON CREATE SET
            e.discovered_at = $discovered_at,
            e.link_raw = link.link_raw,
            e._new = true
        ON MATCH SET
            e._new = false,
            e.link_raw = coalesce(link.link_raw, e.link_raw)
        WITH sum(CASE WHEN e._new THEN 1 ELSE 0 END) AS inserted
        RETURN inserted
        """,
    "endorsement_graph": """
        MATCH (source:Group)-[e:ENDORSES]->(target:Group)
        RETURN source AS g1, e AS rel, target AS g2
        LIMIT $N
        """,
    "common_groups_graph": """
        MATCH (u1:User)-[r:RELATED]-(u2:User)
        WHERE id(u1) < id(u2)
        RETURN u1, r, u2
        LIMIT $N
        """,
    "count_group_messages": """
        MATCH (m:Message {group_id: $group_id})
        RETURN count(m) AS total,
               sum(
                   CASE WHEN coalesce(m.users_processed, false) = false THEN 1 ELSE 0 END
               ) AS unprocessed,
               sum(
                   CASE WHEN coalesce(m.links_processed, false) = false
                        AND m.text IS NOT NULL AND trim(m.text) <> ''
                   THEN 1 ELSE 0 END
               ) AS links_unprocessed
        """,
    "list_stored_message_ids": """
        MATCH (m:Message {group_id: $group_id})
        RETURN m.message_id AS message_id
        """,
    "lookup_users_by_ids": """
        MATCH (u:User)
        WHERE u.id IN $user_ids
        RETURN u.id AS id, u.username AS username, u.alias AS alias
        """,
    "min_stored_message_id": """
        MATCH (m:Message {group_id: $group_id})
        RETURN min(m.message_id) AS min_id
        """,
    "unprocessed_message_authors": """
        MATCH (m:Message {group_id: $group_id})
        WHERE coalesce(m.users_processed, false) = false
          AND m.from_user_id IS NOT NULL
        RETURN DISTINCT m.from_user_id AS author_id
        ORDER BY author_id
        """,
    "unprocessed_messages_for_users": """
        MATCH (m:Message {group_id: $group_id})
        WHERE coalesce(m.users_processed, false) = false
          AND m.from_user_id IS NOT NULL
        RETURN m.message_id AS message_id,
               m.from_user_id AS from_user_id
        ORDER BY m.message_id
        """,
    "mark_messages_processed": """
        MATCH (m:Message {group_id: $group_id})
        WHERE coalesce(m.users_processed, false) = false
        SET m.users_processed = true
        RETURN count(m) AS marked
        """,
    "delete_group_data": """
        MATCH (g:Group)
        WHERE g.id = $group_id
        CALL {
            WITH g
            OPTIONAL MATCH (m:Message)
            WHERE m.group_id = $group_id OR (m)-[:IN_GROUP]->(g)
            DETACH DELETE m
            RETURN count(*) AS _
        }
        WITH g
        CALL {
            WITH g
            OPTIONAL MATCH ()-[e:ENDORSES]-(g)
            DELETE e
            RETURN count(*) AS _
        }
        WITH g
        CALL {
            WITH g
            OPTIONAL MATCH (u:User)-[r:MEMBER_OF]->(g)
            DELETE r
            RETURN count(*) AS _
        }
        WITH g
        CALL {
            WITH g
            MATCH (u:User)
            WHERE $group_id IN coalesce(u.group, [])
            SET u.group = [x IN coalesce(u.group, []) WHERE x <> $group_id]
            RETURN count(u) AS _
        }
        WITH g
        DETACH DELETE g
        RETURN $group_id AS deleted_id
        """,
    "list_all_groups": """
        MATCH (g:Group)
        RETURN g.id AS id,
               g.title AS title,
               g.username AS username,
               g.telegram_peer_id AS telegram_peer_id,
               g.telegram_url AS telegram_url,
               g.user_counts AS user_counts,
               g.aliases AS aliases
        """,
    "merge_member_of_to_winner": """
        MATCH (dup:Group {id: $dup_id})
        MATCH (winner:Group {id: $winner_id})
        MATCH (u:User)-[r:MEMBER_OF]->(dup)
        MERGE (u)-[:MEMBER_OF]->(winner)
        DELETE r
        """,
    "migrate_messages_dup_to_winner": """
        MATCH (m:Message {group_id: $dup_id})
        OPTIONAL MATCH (existing:Message {group_id: $winner_id, message_id: m.message_id})
        WITH m, existing, $winner_id AS winner_id
        FOREACH (_ IN CASE WHEN existing IS NULL THEN [1] ELSE [] END |
            SET m.group_id = winner_id
        )
        FOREACH (_ IN CASE WHEN existing IS NOT NULL THEN [1] ELSE [] END |
            DETACH DELETE m
        )
        WITH winner_id
        MATCH (winner:Group {id: winner_id})
        MATCH (m:Message {group_id: winner_id})
        MERGE (m)-[:IN_GROUP]->(winner)
        RETURN count(m) AS relinked
        """,
    "list_message_ids_for_group": """
        MATCH (m:Message {group_id: $group_id})
        RETURN m.message_id AS message_id
        """,
    "rewire_endorses_dup_to_winner": """
        MATCH (dup:Group {id: $dup_id})
        MATCH (winner:Group {id: $winner_id})
        OPTIONAL MATCH (dup)-[e:ENDORSES]->(t:Group)
        MERGE (winner)-[e2:ENDORSES {message_id: e.message_id}]->(t)
        SET e2.discovered_at = coalesce(e.discovered_at, e2.discovered_at),
            e2.link_raw = coalesce(e.link_raw, e2.link_raw)
        DELETE e
        WITH dup, winner
        OPTIONAL MATCH (s:Group)-[e:ENDORSES]->(dup)
        MERGE (s)-[e2:ENDORSES {message_id: e.message_id}]->(winner)
        SET e2.discovered_at = coalesce(e.discovered_at, e2.discovered_at),
            e2.link_raw = coalesce(e.link_raw, e2.link_raw)
        DELETE e
        """,
    "rewrite_user_group_list": """
        MATCH (u:User)
        WHERE ANY(x IN coalesce(u.group, []) WHERE x IN $alias_ids)
        SET u.group = [x IN coalesce(u.group, []) |
            CASE WHEN x IN $alias_ids THEN $winner_id ELSE x END]
        """,
    "relink_messages_in_group_rel": """
        MATCH (m:Message {group_id: $winner_id})
        MATCH (winner:Group {id: $winner_id})
        MERGE (m)-[:IN_GROUP]->(winner)
        """,
    "detach_delete_group": """
        MATCH (g:Group {id: $group_id})
        DETACH DELETE g
        """,
    "merge_same_property_group_id": """
        MATCH (g:Group)
        WITH g.id AS group_id, collect(g) AS nodes
        WHERE size(nodes) > 1
        WITH group_id, nodes[0] AS winner, tail(nodes) AS dups
        UNWIND dups AS dup
        OPTIONAL MATCH (m:Message)-[:IN_GROUP]->(dup)
        SET m.group_id = group_id
        MERGE (m)-[:IN_GROUP]->(winner)
        WITH winner, dup
        DETACH DELETE dup
        RETURN count(*) AS merged_nodes
        """,
    "recompute_group_member_count": """
        MATCH (g:Group {id: $group_id})
        OPTIONAL MATCH (u:User)-[:MEMBER_OF]->(g)
        WITH g, count(u) AS member_count
        SET g.user_counts = member_count
        RETURN member_count
        """,
    "ensure_group_id_unique": """
        CREATE CONSTRAINT group_id_unique IF NOT EXISTS
        FOR (g:Group) REQUIRE g.id IS UNIQUE
        """,
    "ensure_incident_constraints": """
        CREATE CONSTRAINT incident_id_unique IF NOT EXISTS
        FOR (i:Incident) REQUIRE i.id IS UNIQUE
        """,
    "ensure_watchlist_channel_ref_unique": """
        CREATE CONSTRAINT watchlist_channel_ref_unique IF NOT EXISTS
        FOR (w:WatchlistChannel) REQUIRE w.channel_ref IS UNIQUE
        """,
    "ensure_incident_monitor_config_id": """
        CREATE CONSTRAINT incident_monitor_config_id IF NOT EXISTS
        FOR (c:IncidentMonitorConfig) REQUIRE c.id IS UNIQUE
        """,
    "upsert_incident_monitor_config": """
        MERGE (c:IncidentMonitorConfig {id: 'default'})
        SET c.global_keywords = coalesce($global_keywords, c.global_keywords, []),
            c.global_keywords_enabled = coalesce($global_keywords_enabled, c.global_keywords_enabled, false),
            c.fetch_interval_sec = coalesce($fetch_interval_sec, c.fetch_interval_sec, 300),
            c.scheduler_enabled = coalesce($scheduler_enabled, c.scheduler_enabled, false),
            c.last_fetch_at = coalesce($last_fetch_at, c.last_fetch_at),
            c.run_pipeline_after_fetch = coalesce($run_pipeline_after_fetch, c.run_pipeline_after_fetch, true),
            c.updated_at = $updated_at
        RETURN c
        """,
    "get_incident_monitor_config": """
        MERGE (c:IncidentMonitorConfig {id: 'default'})
        ON CREATE SET
            c.global_keywords = [],
            c.global_keywords_enabled = false,
            c.fetch_interval_sec = 300,
            c.scheduler_enabled = false,
            c.run_pipeline_after_fetch = true
        RETURN c.id AS id,
               coalesce(c.global_keywords, []) AS global_keywords,
               coalesce(c.global_keywords_enabled, false) AS global_keywords_enabled,
               coalesce(c.fetch_interval_sec, 300) AS fetch_interval_sec,
               coalesce(c.scheduler_enabled, false) AS scheduler_enabled,
               c.last_fetch_at AS last_fetch_at,
               coalesce(c.run_pipeline_after_fetch, true) AS run_pipeline_after_fetch
        """,
    "upsert_watchlist_channel": """
        MERGE (w:WatchlistChannel {channel_ref: $channel_ref})
        SET w.enabled = coalesce($enabled, w.enabled, true),
            w.title = coalesce($title, w.title),
            w.last_polled_at = coalesce($last_polled_at, w.last_polled_at),
            w.last_message_id = coalesce($last_message_id, w.last_message_id),
            w.keywords = coalesce($keywords, w.keywords, []),
            w.keywords_enabled = coalesce($keywords_enabled, w.keywords_enabled, false),
            w.use_global_keywords = coalesce($use_global_keywords, w.use_global_keywords, true),
            w.updated_at = $updated_at
        RETURN w.channel_ref AS channel_ref
        """,
    "list_watchlist_channels": """
        MATCH (w:WatchlistChannel)
        RETURN w.channel_ref AS channel_ref,
               coalesce(w.enabled, true) AS enabled,
               w.title AS title,
               w.last_polled_at AS last_polled_at,
               w.last_message_id AS last_message_id,
               coalesce(w.keywords, []) AS keywords,
               coalesce(w.keywords_enabled, false) AS keywords_enabled,
               coalesce(w.use_global_keywords, true) AS use_global_keywords
        ORDER BY w.channel_ref
        """,
    "get_watchlist_channel": """
        MATCH (w:WatchlistChannel {channel_ref: $channel_ref})
        RETURN w.channel_ref AS channel_ref,
               coalesce(w.enabled, true) AS enabled,
               coalesce(w.keywords, []) AS keywords,
               coalesce(w.keywords_enabled, false) AS keywords_enabled,
               coalesce(w.use_global_keywords, true) AS use_global_keywords
        """,
    "delete_watchlist_channel": """
        MATCH (w:WatchlistChannel {channel_ref: $channel_ref})
        DETACH DELETE w
        """,
    "messages_pending_keyword_prefilter": """
        MATCH (m:Message)
        WHERE m.text IS NOT NULL AND trim(m.text) <> ''
          AND coalesce(m.incident_checked, 0) = 0
          AND coalesce(m.incident_pipeline_stage, 'new') IN ['new', 'ingested', '']
        RETURN m.group_id AS group_id,
               m.message_id AS message_id,
               m.text AS text,
               m.date AS date
        ORDER BY m.date DESC
        LIMIT $limit
        """,
    "messages_pending_clean": """
        MATCH (m:Message)
        WHERE m.text IS NOT NULL AND trim(m.text) <> ''
          AND m.incident_pipeline_stage = 'keyword_passed'
          AND (m.text_clean IS NULL OR trim(m.text_clean) = '')
        RETURN m.group_id AS group_id,
               m.message_id AS message_id,
               m.text AS text,
               m.date AS date
        ORDER BY m.date DESC
        LIMIT $limit
        """,
    "messages_pending_filter": """
        MATCH (m:Message)
        WHERE m.text_clean IS NOT NULL AND trim(m.text_clean) <> ''
          AND coalesce(m.incident_checked, 0) = 0
        RETURN m.group_id AS group_id,
               m.message_id AS message_id,
               m.text_clean AS text_clean,
               m.date AS date
        ORDER BY m.date DESC
        LIMIT $limit
        """,
    "messages_pending_dedupe": """
        MATCH (m:Message)
        WHERE m.incident_checked = 1
          AND coalesce(m.incident_processed, 0) = 0
        RETURN m.group_id AS group_id,
               m.message_id AS message_id,
               m.text_clean AS text_clean,
               m.date AS date
        ORDER BY m.date
        LIMIT $limit
        """,
    "messages_pending_extract": """
        MATCH (m:Message)
        WHERE m.incident_checked = 1
          AND m.incident_processed = 1
          AND (m.category IS NULL OR trim(m.category) = '')
        RETURN m.group_id AS group_id,
               m.message_id AS message_id,
               m.text_clean AS text_clean,
               m.date AS date
        ORDER BY m.date DESC
        LIMIT $limit
        """,
    "messages_pending_geocode": """
        MATCH (m:Message)
        WHERE m.incident_checked = 1
          AND m.incident_processed = 1
          AND m.category IS NOT NULL AND trim(m.category) <> ''
          AND m.location_text IS NOT NULL AND trim(m.location_text) <> ''
          AND (m.lat IS NULL OR m.lon IS NULL)
        RETURN m.group_id AS group_id,
               m.message_id AS message_id,
               m.text_clean AS text_clean,
               m.category AS category,
               m.location_text AS location_text,
               m.date AS date
        ORDER BY m.date DESC
        LIMIT $limit
        """,
    "messages_pending_incident_link": """
        MATCH (m:Message)
        WHERE m.incident_checked = 1
          AND m.incident_processed = 1
          AND m.lat IS NOT NULL AND m.lon IS NOT NULL
          AND NOT (m)-[:REPORTS]->(:Incident)
        RETURN m.group_id AS group_id,
               m.message_id AS message_id,
               m.text_clean AS text_clean,
               m.category AS category,
               m.location_text AS location_text,
               m.lat AS lat,
               m.lon AS lon,
               m.date AS date
        ORDER BY m.date DESC
        LIMIT $limit
        """,
    "update_message_incident_fields": """
        MATCH (m:Message {group_id: $group_id, message_id: $message_id})
        SET m.text_clean = coalesce($text_clean, m.text_clean),
            m.incident_checked = coalesce($incident_checked, m.incident_checked),
            m.incident_processed = coalesce($incident_processed, m.incident_processed),
            m.category = coalesce($category, m.category),
            m.location_text = coalesce($location_text, m.location_text),
            m.lat = coalesce($lat, m.lat),
            m.lon = coalesce($lon, m.lon),
            m.incident_pipeline_stage = coalesce($pipeline_stage, m.incident_pipeline_stage)
        RETURN m.message_id AS message_id
        """,
    "merge_incident_from_message": """
        MATCH (m:Message {group_id: $group_id, message_id: $message_id})
        MERGE (i:Incident {id: $incident_id})
        ON CREATE SET
            i.category = $category,
            i.location_text = $location_text,
            i.lat = $lat,
            i.lon = $lon,
            i.occurred_at = $occurred_at,
            i.summary = coalesce($summary, m.text_clean),
            i.dedupe_cluster_id = $dedupe_cluster_id,
            i.created_at = $created_at,
            i.source_group_id = $group_id
        ON MATCH SET
            i.category = coalesce($category, i.category),
            i.location_text = coalesce($location_text, i.location_text),
            i.lat = coalesce($lat, i.lat),
            i.lon = coalesce($lon, i.lon),
            i.summary = coalesce($summary, i.summary)
        MERGE (m)-[:REPORTS]->(i)
        WITH i, m
        OPTIONAL MATCH (g:Group {id: m.group_id})
        FOREACH (_ IN CASE WHEN g IS NOT NULL THEN [1] ELSE [] END |
            MERGE (i)-[:FROM_CHANNEL]->(g)
        )
        RETURN i.id AS incident_id
        """,
    "link_message_to_incident": """
        MATCH (m:Message {group_id: $group_id, message_id: $message_id})
        MATCH (i:Incident {id: $incident_id})
        MERGE (m)-[:REPORTS]->(i)
        SET m.incident_processed = -1
        RETURN count(m) AS linked
        """,
    "incident_pipeline_counts": """
        MATCH (m:Message)
        WHERE m.text IS NOT NULL AND trim(m.text) <> ''
        RETURN
          sum(CASE WHEN coalesce(m.incident_checked, 0) = 0
                    AND coalesce(m.incident_pipeline_stage, 'new') IN ['new', 'ingested', '']
               THEN 1 ELSE 0 END) AS pending_keyword,
          sum(CASE WHEN m.incident_pipeline_stage = 'keyword_passed'
                    AND (m.text_clean IS NULL OR trim(m.text_clean) = '')
               THEN 1 ELSE 0 END) AS pending_clean,
          sum(CASE WHEN m.text_clean IS NOT NULL AND coalesce(m.incident_checked, 0) = 0 THEN 1 ELSE 0 END) AS pending_filter,
          sum(CASE WHEN m.incident_checked = 1 AND coalesce(m.incident_processed, 0) = 0 THEN 1 ELSE 0 END) AS pending_dedupe,
          sum(CASE WHEN m.incident_checked = 1 AND m.incident_processed = 1 AND (m.category IS NULL OR trim(m.category) = '') THEN 1 ELSE 0 END) AS pending_extract,
          sum(CASE WHEN m.incident_checked = 1 AND m.incident_processed = 1 AND m.category IS NOT NULL AND (m.lat IS NULL OR m.lon IS NULL) THEN 1 ELSE 0 END) AS pending_geocode,
          sum(CASE WHEN m.incident_checked = 1 AND m.incident_processed = 1 AND m.lat IS NOT NULL AND NOT (m)-[:REPORTS]->(:Incident) THEN 1 ELSE 0 END) AS pending_link
        """,
    "list_incidents_for_map": """
        MATCH (i:Incident)
        WHERE i.lat IS NOT NULL AND i.lon IS NOT NULL
          AND ($date_from IS NULL OR i.occurred_at >= $date_from)
          AND ($date_to IS NULL OR i.occurred_at <= $date_to)
          AND ($category IS NULL OR i.category = $category)
        RETURN i.id AS id,
               i.category AS category,
               i.location_text AS location_text,
               i.lat AS lat,
               i.lon AS lon,
               i.occurred_at AS occurred_at,
               i.summary AS summary,
               i.source_group_id AS source_group_id
        ORDER BY i.occurred_at DESC
        LIMIT $limit
        """,
    "messages_for_dedupe_by_date": """
        MATCH (m:Message)
        WHERE m.incident_checked = 1
          AND coalesce(m.incident_processed, 0) = 0
          AND m.date IS NOT NULL
          AND ($date_prefix IS NULL OR m.date STARTS WITH $date_prefix)
        RETURN m.group_id AS group_id,
               m.message_id AS message_id,
               m.text_clean AS text_clean,
               m.date AS date
        ORDER BY m.date
        LIMIT $limit
        """,
}

"""     
SUCH A BAD IDEA (n^2 time complexity)

WITH collect(user) AS users
UNWIND range(0, size(users)-2) AS i
UNWIND range(i+1, size(users)-1) AS j
MATCH (u1:User), (u2:User)
WHERE u1 = users[i] AND u2 = users[j]
MERGE (u1)-[r1:SAME_GROUP]-(u2)
SET r1.count = coalesce(r1.count, 0) + 1
"""

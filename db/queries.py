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

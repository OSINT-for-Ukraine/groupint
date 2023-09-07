query_dict = {
    '*N':
        """
        MATCH (n:User) RETURN n LIMIT $N
        """,

    #  problem here the same group update groups_count for user
    'creator_query':
        """
        MERGE (group:Group {id: $group_id})
        SET group += $group_properties
        WITH group
        UNWIND $user_nodes AS user_node
        MERGE (user:User {id: user_node.id})
        SET user += user_node
        SET user.groups_count = coalesce(user.groups_count, 0) + 1
        MERGE (user)-[:MEMBER_OF]->(group)
        """,

    'intersection_more_than_N':  # retrieve the users with more than N intersection in the same groups
        """
        MATCH (u1:User)-[:MEMBER_OF]->(g:Group)<-[:MEMBER_OF]-(u2:User)
        WHERE u1 <> u2
        WITH u1, u2, COLLECT(DISTINCT g) AS commonGroups
        WHERE SIZE(commonGroups) > $N
        RETURN u1, u2
        """,

    'more_than_N_groups':  # retrieve the users with more than N groups
        """
        MATCH (u:User)
        WHERE u.groups_count > $N
        RETURN *
        ORDER BY u.groups_count DESC
        """,

    'the_most_groups_per_user':  # retrieve the users with the most groups
        """
        MATCH (u:User) 
        WITH MAX(u.groups_count) AS max_groups
        MATCH (u:User)
        WHERE u.groups_count = max_groups
        RETURN u
        """,

    'size_rating_for_groups':  # retrieve a rating of the groups ordered by the size
        """
        MATCH (g:Group) 
        RETURN g.id, g.title, g.user_counts 
        ORDER BY g.user_counts DESC
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

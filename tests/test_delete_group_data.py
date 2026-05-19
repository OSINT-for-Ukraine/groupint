import unittest

from db.dal import GraphManager
from db.config import graph


class TestDeleteGroupData(unittest.TestCase):
    def test_delete_unknown_group_returns_zero(self) -> None:
        ref = "__no_such_groupint_test_ref__"
        self.assertEqual(GraphManager.delete_group_data(ref), 0)

    def test_delete_round_trip(self) -> None:
        ref = "__groupint_delete_test__"
        graph.run(
            """
            MERGE (g:Group {id: $group_id})
            SET g.title = 'delete test'
            MERGE (u:User {id: 999999001})
            MERGE (u)-[:MEMBER_OF]->(g)
            MERGE (m:Message {group_id: $group_id, message_id: 1})
            SET m.text = 'x'
            MERGE (m)-[:IN_GROUP]->(g)
            """,
            {"group_id": ref},
        )
        deleted = GraphManager.delete_group_data(ref)
        self.assertGreaterEqual(deleted, 1)
        remaining = graph.run(
            "MATCH (g:Group) WHERE g.id = $group_id RETURN count(g) AS c",
            {"group_id": ref},
        ).data()[0]["c"]
        self.assertEqual(int(remaining), 0)
        msgs = graph.run(
            "MATCH (m:Message {group_id: $group_id}) RETURN count(m) AS c",
            {"group_id": ref},
        ).data()[0]["c"]
        self.assertEqual(int(msgs), 0)


if __name__ == "__main__":
    unittest.main()

from typing import Type, Union

from py2neo import Node
from py2neo.integration import Table

from db.config import graph
from db.queries import query_dict
from models import FetchedChannel


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
    def fetch_data(
        query_key: str, n: int = None, out_type: str = "map"
    ) -> Union[Table, dict, Type["DataFrame"]]:
        query = query_dict.get(query_key)
        raw_result = graph.run(query, parameters={"N": n})
        match out_type:
            case "table":
                result = (
                    raw_result.to_table()
                )  # вывод таблицы <class 'py2neo.integration.Table'>
            case "dframe":
                result = raw_result.to_data_frame()  # for pandas
            case "map":
                result = raw_result.data()  # вывод в dict
            case _:
                raise AttributeError("Here is no such type of output data")
        return result

    @staticmethod
    def export_data() -> str:
        result = graph.run("MATCH (n:User) RETURN n").data()
        res_arr = ["Label,Type,ID,Description,Tags"]
        for node in result:
            res_arr.append(
                "{},Person,{},{},{}".format(
                    node["n"].get("alias", ""),
                    node["n"].get("id", ""),
                    node["n"].get("username", ""),
                    "|".join(node["n"].get("group", [])),
                )
            )
        return "\n".join(res_arr)

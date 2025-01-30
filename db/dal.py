import json
import csv
from io import StringIO
from typing import Type, Union

from py2neo import Node
from py2neo.integration import Table

from db.config import graph
from db.queries import query_dict
from models import FetchedChannel


class GraphManager:

    @classmethod
    def add_user(cls, user: tuple, groups: list) -> None:
        parameters = {
            "user_id": user[0],
            "username": user[1],
            "alias": user[2],
            "groups": groups,
        }
        graph.run(query_dict.get("add_user"), parameters)

    @classmethod
    def create_relationships(cls, group_id: str = "") -> None:
        graph.run(query_dict.get("create_relationship_between_users_of_same_groups"))
        return cls.fetch_data("ignore_group_intersection", out_type="csv", group_id=group_id)

    @classmethod
    def add_fetched_channel(cls, instance: FetchedChannel) -> None:
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

    @classmethod
    def fetch_data(
        cls, query_key: str, n: int = None, out_type: str = "map", group_id: str = "", target_user: str = ""
    ) -> Union[Table, dict, Type["DataFrame"], str]:
        query = query_dict.get(query_key)
        raw_result = graph.run(query, parameters={"N": n, "G": group_id})
        match out_type:
            case "table":
                result = (
                    raw_result.to_table()
                )  # вывод таблицы <class 'py2neo.integration.Table'>
            case "dframe":
                result = raw_result.to_data_frame()  # for pandas
            case "map":
                result = raw_result.data()  # вывод в dict
            case "csv":
                result = cls.convert_data_to_csv(raw_result.data(), target_user)
            case _:
                raise AttributeError("Here is no such type of output data")
        return result

    @classmethod
    def convert_data_to_csv(cls, data: list, target_user: str = "") -> str:
        list_data = [["Alias", "Username", "Id", "Group", "TargetUser"]]
        for record in data:
            node = record.get("n")
            if not node:
                continue
            mark_user = 1 if node.get("username") else 0
            list_data.append([node.get("alias"), node.get("username"), node.get("id"), ";".join(node.get("group", [])), mark_user])
        buffer = StringIO()
        writer = csv.writer(buffer, delimiter=':', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for row in list_data:
            writer.writerow(row)
        return buffer.getvalue()

    @classmethod
    def convert_data_to_json(cls, data: list, target_user: str = "") -> str:
        list_data = list()
        for record in data:
            node = record.get("n")
            if not node:
                continue
            mark_user = 1 if node.get("username") else 0
            list_data.append(
                {
                    "alias": node.get("alias"),
                    "username": node.get("username"),
                    "id": node.get("id"),
                    "group": node.get("group"),
                    "mark_user": mark_user,
                }
            )
        return json.dumps(list_data)

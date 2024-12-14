from typing import Literal, Optional, Type, Union

from py2neo.integration import Table
from telethon.sync import TelegramClient

from core.tg_api_connector import ChannelParser
from db.dal import GraphManager
from models import FetchedChannel


async def entry(client: TelegramClient, channel: Union[str, int]) -> FetchedChannel:
    parser = ChannelParser(client)
    await parser.start()
    await parser.join_channel(channel)
    channel_instance = await parser.get_all_participants(channel)
    return channel_instance


class DataManager:

    @classmethod
    async def load_data(cls, client: TelegramClient, channel: Union[str, int]) -> None:
        fetched_channel = await entry(client, channel)
        GraphManager.add_fetched_channel(fetched_channel)

    @classmethod
    async def add_user(cls, user: tuple, groups: list) -> None:
        GraphManager.add_user(user, groups)

    # @staticmethod
    # async def add_user(user: tuple) -> None:
    #    GraphManager.add_user(user)  # TODO return to previous params

    @classmethod
    async def create_relationships(cls, group_id: str = "") -> None:
        return GraphManager.create_relationships(group_id)

    @classmethod
    async def get_data(
        cls, query: str, n: Optional[int] = None, group_id: str = "", target_user: str = ""
    ) -> Union[Table, dict, Type["DataFrame"]]:
        return GraphManager.fetch_data(query, n=n, group_id=group_id, target_user=target_user)

    @classmethod
    def data_to_str_format(cls, data: list, out: Literal["csv", "json"], target_user: str = "") -> str:
        match out:
            case "csv":
                return GraphManager.convert_data_to_csv(data, target_user)
            case "json":
                return GraphManager.convert_data_to_json(data, target_user)
            case _:
                raise ValueError("Unsupported convert type")
        return ""

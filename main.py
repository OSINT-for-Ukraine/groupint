import datetime
import os
from typing import Union, Type, Optional
from py2neo.integration import Table

from core.tg_api_connector import ChannelParser
from db.dal import GraphManager
from models import FetchedChannel
from telethon.sync import TelegramClient


async def entry(client: TelegramClient, channel: Union[str, int]) -> FetchedChannel:
    parser = ChannelParser(client)
    await parser.start()
    await parser.join_channel(channel)
    channel_instance = await parser.get_all_participants(channel)
    return channel_instance


class DataManager:

    @staticmethod
    async def load_data(client: TelegramClient, channel: Union[str, int]) -> None:
        fetched_channel = await entry(client, channel)
        GraphManager.add_fetched_channel(fetched_channel)

    @staticmethod
    async def get_data(query: str, n: Optional[int] = None) -> Union[Table, dict, Type['DataFrame']]:
        return GraphManager.fetch_data(query, n)

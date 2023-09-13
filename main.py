import datetime
import os
from typing import Union, Type, Optional
from py2neo.integration import Table

from core.tg_api_connector import ChannelParser
from db.dal import GraphManager
from models import FetchedChannel


async def entry(API_ID, API_HASH, PHONE, BOT_TOKEN, channel: Union[str, int]) -> FetchedChannel:
    session_path = os.path.join(os.getcwd(), f'{PHONE}.session')
    parser = ChannelParser(API_ID, API_HASH, PHONE, BOT_TOKEN)
    parser.client = session_path
    await parser.start()
    await parser.join_channel(channel)
    channel_instance = await parser.get_all_participants(channel)
    return channel_instance


class DataManager:

    @staticmethod
    async def load_data(channel: Union[str, int], API_ID, API_HASH, PHONE, BOT_TOKEN) -> None:
        fetched_channel = await entry(channel, API_ID, API_HASH, PHONE, BOT_TOKEN)
        GraphManager.add_fetched_channel(fetched_channel)

    @staticmethod
    async def get_data(query: str, n: Optional[int] = None) -> Union[Table, dict, Type['DataFrame']]:
        return GraphManager.fetch_data(query, n)

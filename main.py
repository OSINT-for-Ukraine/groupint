import datetime
from typing import Union, Type, Optional
from py2neo.integration import Table
from core.tg_api_connector import entry
from db.dal import GraphManager


class DataManager:

    @staticmethod
    async def load_data(channel: Union[str, int]) -> None:
        fetched_channel = await entry(channel)
        GraphManager.add_fetched_channel(fetched_channel)

    @staticmethod
    async def get_data(query: str, n: Optional[int] = None) -> Union[Table, dict, Type['DataFrame']]:
        return GraphManager.fetch_data(query, n)

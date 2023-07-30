import asyncio
import datetime
from typing import Union, Type
from py2neo.integration import Table
from core.tg_api_connector import entry
from db.dal import GraphManager


class DataManager:

    @staticmethod
    async def load_data(channel: Union[str, int]) -> None:
        start = datetime.datetime.now()
        fetched_channel = await entry(channel)
        print('Channel has been fetched')
        GraphManager.add_fetched_channel(fetched_channel)
        end = datetime.datetime.now()
        print(f'Execution time {end - start}')

    @staticmethod
    async def get_data() -> Union[Table, dict, Type['DataFrame']]:
        return GraphManager.fetch_data('*N', 200)


asyncio.run(DataManager.load_data('fastapiru'))

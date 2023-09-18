import asyncio
import datetime
import os.path
from typing import Union, Optional, AsyncGenerator
from telethon.errors import ChannelInvalidError, ChannelPrivateError, InputConstructorInvalidError, \
    ChatAdminRequiredError, MsgIdInvalidError
from telethon.sync import TelegramClient
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import GetRepliesRequest
from telethon.tl.types import User, Channel, Chat, PeerUser
from models import FetchedChannel, FetchedUser, FetchedUserFromGroup




class ChannelParser:

    def __init__(self, api_id: int, api_hash: str, phone: str, bot_token: Optional[str] = None):
        self._api_id = api_id
        self._api_hash = api_hash
        self._phone = phone
        self._bot_token = bot_token
        self._client = None

    @property
    def client(self) -> TelegramClient:
        return self._client

    @client.setter
    def client(self, client_name: str):
        if self._client is None:
            self._client = TelegramClient(client_name, self._api_id, self._api_hash)
        else:
            print("Client is already set")

    # async def start(self) -> None:
    #     await self.client.start()

    async def about_me(self) -> User:
        return await self.client.get_me()

    async def update_name(self, name: str) -> None:
        await self.client(UpdateProfileRequest(first_name=name))

    async def send_message(self, user_id: str, message: str) -> None:
        await self.client.send_message(user_id, message)

    async def join_channel(self, channel: Union[str, int]) -> None:
        if isinstance(channel, int):
            await self.client(JoinChannelRequest(channel=channel))
        else:
            await self.client(JoinChannelRequest(channel=f'@{channel}'))

    async def leave_channel(self, channel: Union[str, int]) -> None:
        if isinstance(channel, int):
            await self.client(LeaveChannelRequest(channel=channel))
        else:
            await self.client(LeaveChannelRequest(channel=f'@{channel}'))

    async def get_all_participants(self, channel: Union[str, int]) -> FetchedChannel:
        channel_data = FetchedChannel()
        try:
            if isinstance(channel, int):
                entity = await self.client.get_entity(channel)
            else:
                entity = await self.client.get_entity(f'@{channel}')
            channel_data.id = entity.id
            channel_data.title = entity.title
            if entity.broadcast:
                print('Chanel')
                users_messages_set = await self.get_comments_from_channel(entity)  # here is data with messages !!!
                user_set = {(user.user_id, user.user_name, user.first_name) for user in users_messages_set}
                user_array = list(user_set)
                channel_data.user_set = user_array
                channel_data.user_counts = len(user_array)
                return channel_data
            else:
                print('Group')
                async for members in self.get_chunked_participants(entity.id):
                    channel_data.user_set.extend(
                        [(user.id, user.username or 'NULL', user.first_name or 'NULL') async for user in members])
                channel_data.user_counts = len(channel_data.user_set)
                print(channel_data.user_counts)
                users_messages_set = await self.get_comments_from_chat(entity)  # here is data with messages !!!
                return channel_data
        except (ChannelInvalidError, ChannelPrivateError, ChatAdminRequiredError,
                InputConstructorInvalidError, TimeoutError) as e:
            print(str(e))

    async def get_chunked_participants(self, channel: Union[str, int], limit: int = 5000,  # CONFIG
                                       key_word: str = '') -> AsyncGenerator:
        participants = self.client.iter_participants(entity=channel, limit=limit, search=key_word)
        yield participants

    async def get_comments_from_chat(self, chat_entity: Chat) -> list[FetchedUserFromGroup]:
        messages = self.client.iter_messages(chat_entity, limit=1)  # CONFIG
        users_messages_set = []
        async for message in messages:
            try:
                user_message = FetchedUserFromGroup(
                    user_id=message.from_id.user_id,
                    message=message.message if message.message else 'NULL',
                    channel_id=chat_entity.id if chat_entity.id else 'NULL',
                    channel_title=chat_entity.title if chat_entity.title else 'NULL'
                )
                users_messages_set.append(user_message)
            except AttributeError:
                ...
        return users_messages_set

    async def get_comments_from_channel(self, channel_entity: Channel) -> list[FetchedUser]:
        posts = await self.client.get_messages(channel_entity, limit=50)  # CONFIG
        messages = []
        for post in posts:
            if post.id:
                try:
                    channel_messages = await self.client(GetRepliesRequest(
                        peer=channel_entity,
                        msg_id=post.id,
                        offset_id=0,
                        limit=0,
                        max_id=0,
                        min_id=0,
                        hash=0,
                        offset_date=None,
                        add_offset=0
                    ))
                    messages.extend(channel_messages.messages)
                except MsgIdInvalidError:
                    pass
        users_messages_set = []
        for message in messages:
            if isinstance(message.from_id, PeerUser):
                user_id = message.from_id.user_id
                user = await self.client.get_entity(user_id)
                user_message = FetchedUser(
                    user_id=user.id,
                    user_name=user.username if user.username else 'NULL',
                    first_name=user.first_name if user.first_name else 'NULL',
                    last_name=user.last_name if user.last_name else 'NULL',
                    phone=user.phone if user.phone else 'NULL',
                    message=message.message if message.message else 'NULL',
                    channel_id=channel_entity.id if channel_entity.id else 'NULL',
                    channel_title=channel_entity.title if channel_entity.title else 'NULL'
                )
                users_messages_set.append(user_message)
        return users_messages_set



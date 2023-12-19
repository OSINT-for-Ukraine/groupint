import asyncio
from typing import Union, AsyncGenerator
from telethon.errors import ChannelInvalidError, ChannelPrivateError, InputConstructorInvalidError, \
    ChatAdminRequiredError, MsgIdInvalidError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import GetRepliesRequest
from telethon.tl.types import User, Channel, Chat, PeerUser, PeerChannel
from models import FetchedChannel, FetchedUser, FetchedUserFromGroup

from telethon import TelegramClient
from telethon.tl.functions.contacts import ResolveUsernameRequest

import re


async def is_user_authorized(client):
    return await client.is_user_authorized()


async def create_client(phone_number, API_ID, API_HASH):
    client_tg = TelegramClient(phone_number, API_ID, API_HASH)
    await client_tg.connect()
    return client_tg


async def generate_otp(client_tg, phone_number):
    result = await client_tg.send_code_request(
        phone=phone_number
    )
    phone_hash = result.phone_code_hash
    return client_tg, phone_hash


async def verify_otp(client, phone, secret_code, phone_hash):
    await client.connect()
    await client.sign_in(
        phone=phone,
        code=secret_code,
        phone_code_hash=phone_hash,
    )


async def send_message(client, message, user="me"):
    await client.send_message(entity=user, message=message)


async def get_messages(client, user="me"):
    output=""
    async for message in client.iter_messages(entity=user):
        output += f"""{message.id}\n{message.text}\n"""
        if message.buttons:
            output += f"""{[button[0].text for button in message.buttons]}"""
    return output


async def get_all_participants(client, channel):
    channel = await client(ResolveUsernameRequest(channel))
    users = []
    async for _user in client.iter_participants(entity=channel):
        users.append((_user.id,_user.username))
    return users
    # if entity.broadcast:
    #     print('Chanel')
    #     users_messages_set = await self.get_comments_from_channel(entity)  # here is data with messages !!!
    #     user_set = {(user.user_id, user.user_name, user.first_name) for user in users_messages_set}
    #     user_array = list(user_set)
    #     return user_array

async def get_participants_based_on_messages(client, channel, limit:int=10000):
    entity = await client.get_entity(channel)
    messages = await client.get_messages(entity,limit=limit)
    print("got messages")
    user_set = set()
    for message in messages:
        if type(message.from_id) is PeerUser:
            user_set.add(message.from_id.user_id)
        elif type(message.from_id) is PeerChannel:
            user_set.add(message.from_id.channel_id)
    user_list = []
    for id in user_set:
        user = await client.get_entity(id)
        user_list.append((id,user.username))
    return user_list

async def get_groups_of_which_user_is_part_of(client, user, dry_run=True):
    """
    interacts with telesint bot to query it for the groups, "user" is part of
    client - telethon client
    dry_run - only reads the message sent by telesint bot(good for testing)

    """
    failed_result = []
    if not dry_run:
        await client.send_message(entity="telesint_bot", message=user)
        await asyncio.sleep(5)
    # example of an answer from the bot, specifically the message ends with
    # search button, because the user is in db, otherwise here the result will
    # be that the user is not found and the function returns with empty list
    #  👨‍💼️️ Тип: пользователь

    # 🆔 ID пользователя: 457528096

    # 🔗 Ссылка: https://t.me/total_ordering

    # 👤 Имя: Yegor 𓃰

    # 🗃 Наличие в базе: ✅

    # 🔍 Осталось запросов: 3
    # ['🔍 Искать'] 


    # if the user is in the database we need to click the button "Искать" (search)
    
    if not dry_run:
        async for message in client.iter_messages(entity="telesint_bot", limit=1):
            if message.buttons:
                await message.click(0)
                await asyncio.sleep(10)
            else:
                print("object not in the bot's db")
                return failed_result

    # now we want to read the output and extract the channels
    # pattern used to extract the block of text containing groups names
    answer_to_parse = ""
    async for message in client.iter_messages(entity="telesint_bot", limit=1):
        answer_to_parse = message.text
    pattern_groups_text_block = r"(.|\n)*Открытые группы \[.*?\]:\n((.*\n?)*)" 
    match_obj = re.match(pattern_groups_text_block, answer_to_parse)
    text_block = ""
    if match_obj:
        text_block = match_obj.group(2)
    else:
        print("pattern not found in the message")
        return failed_result

    # example output after extraction of group 1 from regex
    # "@ru_python Python
    # @devops_ru DevOps — русскоговорящее сообщество
    # @procxx pro.cxx
    # ...
    # @groupname <free text>"

    pattern_extract_group_names_text = r"@(.*?)\s.*"
    if re.match(pattern_extract_group_names_text, text_block):
        group_names_text = re.sub(pattern_extract_group_names_text, r"\g<1>", match_obj.group(2))

    return group_names_text.split("\n")


class ChannelParser:
    def __init__(self, client: TelegramClient):
        self.client = client

    async def start(self) -> None:
        await self.client.start()

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

    async def get_chunked_participants(self, channel: Union[str, int],  # CONFIG
                                       key_word: str = '') -> AsyncGenerator:
        participants = self.client.iter_participants(entity=channel, search=key_word)
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



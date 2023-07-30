from typing import Optional
from pydantic import BaseModel


class FetchedChannel(BaseModel):
    id: Optional[int] = None
    title: Optional[str] = None
    user_counts: Optional[int] = None
    user_set: Optional[list[Optional[tuple[int, str, str]]]] = []


class FetchedUser(BaseModel):  # detail about user comment
    user_id: int
    user_name: str
    first_name: str
    last_name: str
    phone: str
    message: str
    channel_id: int
    channel_title: str


class FetchedUserFromGroup(BaseModel):
    user_id: int
    message: str
    channel_id: int
    channel_title: str

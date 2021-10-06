"""Types for helping in type hinting."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from datetime import datetime
    from typing import Literal, Optional

    import bson


class MongoDbDocument(TypedDict):
    """Keys common to all Mongo documents."""

    _id: bson.ObjectId


class StreamData(TypedDict):
    """Data describing a twitch stream in the db."""

    where: str
    url: str


class MemberDocument(MongoDbDocument):
    """Data describing a user in the db."""

    twitch_name: str
    twitch_id: int

    discord_name: Optional[str]
    discord_id: Optional[int]

    points: int
    stream: Optional[StreamData]
    isAdmin: bool  # noqa: N815


class RoleInfoDocument(MongoDbDocument):
    """Data describing a role in the db."""

    role_id: int
    color: str
    description: str
    name: str


class BirthdayDocument(MongoDbDocument):
    """Data describing a birthday in the db."""

    discord_id: int
    date: datetime


# twitch


class _TwitchUserDataBase(TypedDict):
    """Response from the twitch api."""

    brodcaster_type: Literal["partner", "affiliate", ""]
    description: str
    display_name: str
    login: str
    offline_image_url: str
    profile_image_url: str
    type: Literal["staff", "admin", "global_mod", ""]  # noqa: A003
    view_count: int
    created_at: str


class TwitchUserDataRaw(_TwitchUserDataBase):
    """The raw data from the twitch api."""

    id: str  # noqa: A003


class TwitchUserData(_TwitchUserDataBase):
    """The edited date from the twitch api."""

    id: int  # noqa: A003


class TwitchSuccessResponse(TypedDict):
    """Response from the twitch api when everything goes well."""

    data: list[TwitchUserDataRaw]


class TwitchErrorResponse(TypedDict):
    """Response from the twitch api when stuff goes wrong."""

    error: str
    status: int
    message: str


# Possible responses from twitch api
TwitchResponse = TwitchSuccessResponse | TwitchErrorResponse

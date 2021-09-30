from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict, Union

if TYPE_CHECKING:
    from typing import Literal, Optional

    import bson


class StreamData(TypedDict):
    where: str
    url: str


class MemberDocument(TypedDict):
    _id: bson.ObjectId

    twitch_name: str
    twitch_id: int

    discord_name: Optional[str]
    discord_id: Optional[int]

    points: int
    stream: Optional[StreamData]
    isAdmin: bool  # noqa: N815


class RoleInfoDocument(TypedDict):
    _id: bson.ObjectId

    role_id: int
    color: str
    description: str
    name: str


# twitch


class _TwitchUserDataBase(TypedDict):
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
    id: str  # noqa: A003


class TwitchUserData(_TwitchUserDataBase):
    id: int  # noqa: A003


class TwitchSuccessResponse(TypedDict):
    data: list[TwitchUserDataRaw]


class TwitchErrorResponse(TypedDict):
    error: str
    status: int
    message: str


TwitchResponse = Union[TwitchSuccessResponse, TwitchErrorResponse]

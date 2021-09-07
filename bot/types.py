"""
Types used in typhinting.

mainly TypeDicts's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict, Union

if TYPE_CHECKING:
    from typing import List, Optional


class StreamingData(TypedDict):
    """Data stored in db when somebody is streaming."""

    live_url: str
    live_where: str


class MemberData(TypedDict):
    """Data stored on users in db."""

    _id: str
    twitch_name: str
    twitch_id: int
    discord_name: Optional[str]
    discord_id: Optional[str]
    points: int
    isAdmin: bool  # noqa: N815
    stream: Optional[StreamingData]


class TwitchData(TypedDict):
    """Data twitch returns on users."""

    # only fields we care about
    id: int  # noqa: A003 VNE003
    login: str
    profile_image_url: str


class TwitchUserResponseCorrect(TypedDict):
    """Format of a error free response."""

    data: List[TwitchData]


class TwitchUserResponseError(TypedDict):
    """Format of a error response."""

    error: int
    message: str


TwitchUserResponse = Union[TwitchUserResponseCorrect, TwitchUserResponseError]

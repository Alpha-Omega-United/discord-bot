"""Types for helping in type hinting."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from datetime import datetime
    from typing import Literal

    import bson


class MongoDbDocument(TypedDict):
    """Keys common to all Mongo documents."""

    _id: bson.ObjectId


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

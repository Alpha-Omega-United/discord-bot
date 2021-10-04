from __future__ import annotations

from typing import TYPE_CHECKING

import hikari
import tanjun

from bot import constants, injectors

if TYPE_CHECKING:
    from typing import Optional

    from motor import motor_asyncio as motor

    from bot.types import MemberDocument

component = tanjun.Component()


def get_streaming_activity(
    presence: hikari.MemberPresence,
) -> Optional[hikari.Activity]:
    for activity in presence.activities:
        if activity.type == hikari.ActivityType.STREAMING:
            return activity

    return None


def get_member_streaming_activity(
    user: hikari.Member,
) -> Optional[hikari.Activity]:
    presence = user.get_presence()

    if presence is None:
        return None

    return get_streaming_activity(presence)


async def update_streaming_status(
    members: motor.AsyncIOMotorCollection[MemberDocument],
    member_id: int,
    streaming_act: Optional[hikari.Activity],
) -> None:
    if streaming_act is None:
        await members.update_one(
            {"discord_id": str(member_id)}, {"$set": {"stream": None}}
        )
    else:
        await members.update_one(
            {"discord_id": str(member_id)},
            {
                "$set": {
                    "stream": {
                        "live_where": streaming_act.name,
                        "live_url": streaming_act.url,
                    }
                }
            },
        )


@component.with_listener(hikari.StartedEvent)
async def sync_live_channels(
    event: hikari.StartedEvent,
    bot: hikari.GatewayBot = tanjun.injected(type=hikari.GatewayBot),
    members: motor.AsyncIOMotorCollection[MemberDocument] = tanjun.injected(
        callback=injectors.get_members_db
    ),
) -> None:

    guild = await bot.rest.fetch_guild(constants.GUILD_ID)

    for member_id, member in guild.get_members().items():
        streaming_act = get_member_streaming_activity(member)
        await update_streaming_status(members, member_id, streaming_act)


@component.with_listener(hikari.PresenceUpdateEvent)
async def update_member(
    event: hikari.PresenceUpdateEvent,
    bot: hikari.GatewayBot = tanjun.injected(type=hikari.GatewayBot),
    members: motor.AsyncIOMotorCollection[MemberDocument] = tanjun.injected(
        callback=injectors.get_members_db
    ),
) -> None:
    if event.old_presence is not None:
        was_streaming = get_streaming_activity(event.old_presence) is not None
    else:
        was_streaming = False

    streaming_act = get_streaming_activity(event.presence)
    is_streaming = streaming_act is not None

    if was_streaming != is_streaming:
        await update_streaming_status(members, event.user_id, streaming_act)


@tanjun.as_loader
def load_component(client: tanjun.Client) -> None:
    """
    Load component.

    Args:
        client (tanjun.Client): Client to add component to.
    """
    client.add_component(component)

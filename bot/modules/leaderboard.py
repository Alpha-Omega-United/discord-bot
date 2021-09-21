from __future__ import annotations

import time
from typing import TYPE_CHECKING

import hikari
import pymongo
import tanjun
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import constants, injectors
from bot.constants import LEADERBOARD_CHANNEL_ID

if TYPE_CHECKING:
    from motor import motor_asyncio as motor


component = tanjun.Component()


@component.with_listener(hikari.StartedEvent)
async def on_started(
    event: hikari.StartedEvent,
    bot: hikari.GatewayBot = tanjun.injected(type=hikari.GatewayBot),
    members: motor.AsyncIOMotorCollection = tanjun.injected(
        callback=injectors.get_members_db
    ),
    scheduler: AsyncIOScheduler = tanjun.injected(type=AsyncIOScheduler),
) -> None:
    channel = await bot.rest.fetch_channel(LEADERBOARD_CHANNEL_ID)
    if not isinstance(channel, hikari.TextableChannel):
        raise TypeError("Expected text channel.")

    messages = await channel.fetch_history(after=0)

    if messages:
        leaderboard_message = messages[-1]
    else:
        leaderboard_message = await channel.send("TMP")

    scheduler.add_job(
        update_leaderboard,
        "interval",
        args=(leaderboard_message, members),
        minutes=10,
    )


async def update_leaderboard(
    leaderboard_message: hikari.Message, members: motor.AsyncIOMotorCollection
) -> None:
    current_time = int(time.time())

    top_users = members.find().sort("points", pymongo.DESCENDING).limit(10)

    description_lines = []

    async for user in top_users:
        twittch_channel_name = user["twitch_name"]
        twitch_mention = (
            f"[{twittch_channel_name}]"
            f"(https://www.twitch.tv/{twittch_channel_name})"
        )

        if (discord_id := user.get("discord_id")) is not None:
            user_mention = f"<@{discord_id}> / {twitch_mention}"
        else:
            user_mention = twitch_mention

        points = user["points"]
        description_lines.append(f"{user_mention} : **{points}**")

    embed = hikari.Embed(
        title=f"last updated <t:{current_time}:R>",
        color=constants.Colors.YELLOW,
        description="\n".join(description_lines),
    )

    await leaderboard_message.edit(content="", embed=embed)


@tanjun.as_loader
def load_component(client: tanjun.Client) -> None:
    """
    Load component.

    Args:
        client (tanjun.Client): Client to add component to.
    """
    client.add_component(component)

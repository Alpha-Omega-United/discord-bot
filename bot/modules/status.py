"""Bot status."""

import os
import sys
import time

import hikari
import tanjun

from bot import constants

component = tanjun.Component()


@component.with_slash_command
@tanjun.as_slash_command("status", "Get the status of the bot.")
async def command_status(
    ctx: tanjun.abc.SlashContext,
    bot: hikari.GatewayBot = tanjun.injected(type=hikari.GatewayBot),
) -> None:
    """
    Dispat the status of the bot.

    Args:
        ctx (tanjun.abc.SlashContext): The interaction context
        bot (hikari.GatewayBot, optional): hikari bot instace, used to get latency.
    """
    embed = (
        hikari.Embed(title="Bot status", color=constants.Colors.GREEN)
        .add_field(name="os", value=os.uname().release, inline=True)
        .add_field(
            name="python",
            value=".".join(map(str, sys.version_info)),
            inline=True,
        )
        .add_field(name="hikari", value=hikari.__version__, inline=True)
        .add_field(name="tanjun", value=tanjun.__version__, inline=True)
        .add_field(
            name="ping",
            value=f"{bot.heartbeat_latency * 1000 :.0f} ms",
            inline=True,
        )
        .add_field(
            name="started", value=f"<t:{component.metadata['start_time']}:R>"
        )
    )

    await ctx.respond(embed=embed)


@component.with_listener(hikari.StartedEvent)
async def store_start_time(
    event: hikari.StartedEvent,
) -> None:
    """
    Store the time the bot started.

    Args:
        event (hikari.StartedEvent): The start event
    """
    component.metadata["start_time"] = int(time.time())


@component.with_listener(hikari.StartedEvent)
async def send_online_embed(
    event: hikari.StartedEvent,
    rest: hikari.impl.RESTClientImpl = tanjun.injected(
        type=hikari.impl.RESTClientImpl
    ),
) -> None:
    """
    Send an embed when the bot start.

    Args:
        event (hikari.StartedEvent): Start event.
        rest (hikari.impl.RESTClientImpl, optional):
            Rest application to create message with.
    """
    embed = hikari.Embed(
        title="Bot online",
        color=constants.Colors.GREEN,
        description="Bot is online!",
    )

    await rest.create_message(constants.LOG_CHANNEL_ID, embed=embed)


@tanjun.as_loader
def load_component(client: tanjun.Client) -> None:
    """
    Load component.

    Args:
        client (tanjun.abc.Client): Client to add component to.
    """
    client.add_component(component)

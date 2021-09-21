import os
import sys
import time

import hikari
import tanjun

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
        hikari.Embed(title="Bot status", color=hikari.Color(0x07E500))
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
    client: tanjun.Client = tanjun.injected(type=tanjun.Client),
) -> None:
    """
    Store start time.

    Args:
        event (hikari.StartedEvent): StartedEvent.
        client (tanjun.Client, optional): tanjun client to store time on.
    """
    component.metadata["start_time"] = int(time.time())


@tanjun.as_loader
def load_component(client: tanjun.Client) -> None:
    """
    Load component.

    Args:
        client (tanjun.abc.Client): Client to add component to.
    """
    client.add_component(component)

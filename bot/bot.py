"""Bot core."""
import functools

import hikari
import tanjun

from bot import constants, injectors

tanjun.as_slash_command = functools.partial(
    tanjun.as_slash_command, default_to_ephemeral=constants.HIDE_MESSAGES
)


def create_bot() -> hikari.GatewayBot:
    """
    Create bot instace.

    Returns:
        hikari.GatewayBot: The bot instance created.
    """
    intents = hikari.Intents.ALL

    bot = hikari.GatewayBot(constants.TOKEN, intents=intents)
    client = tanjun.Client.from_gateway_bot(
        bot, set_global_commands=constants.GUILD_ID
    ).load_modules(*constants.Paths.modules.glob("*.py"))

    injectors.register_injectors(client)

    return bot

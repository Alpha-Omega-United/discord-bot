"""Bot core."""

import os
import sys
import time
import traceback

import aiohttp
import discord
import discord_slash
import dns.resolver
from discord.ext import commands
from loguru import logger

from bot import constants

# The reason we need this, is that dns lookup fails with default settings,
# so we need to set the dns severs manually,
# so to stop one dns from ruining our day lets use more than one.

# SOLUTION FROM:
# https://forum.omz-software.com/topic/6751/pymongo-errors-configurationerror-resolver-configuration-could-not-be-read-or-specified-no-nameservers/5

dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)  # type: ignore
dns.resolver.default_resolver.nameservers = constants.DNS_SERVERS

import pymongo  # noqa: E402


class Bot(commands.Bot):
    """Classes that manages core bot functions."""

    def __init__(self) -> None:
        """Create Bot."""
        intents = discord.Intents.none()
        intents.members = True
        intents.guilds = True
        intents.presences = True

        super().__init__(
            # to be able to load cogs we need to use commands.Bot,
            # usally commands.bot operats on normal commands.
            # we are going to be using discord_slash we dont need a prefix
            # but since discord.py expects us to they require a prefix anyway
            # so just some spam is a nice work around
            command_prefix="sfsdknfsdoifmsoidoamdoadmoiadjmo",
            intents=intents,
        )

        self.http_session = aiohttp.ClientSession()

        logger.info("Connecting to DB")
        self.db_client = pymongo.MongoClient(constants.DATABASE_URI)
        self.database = self.db_client[constants.DATABASE_NAME]

        self.log_channel: discord.TextChannel

    def load_all_extensions(self) -> None:
        """Load all extensions in constants.Paths.cogs."""
        for extension_file in constants.Paths.cogs.glob("*.py"):
            dot_path = str(extension_file).replace(os.sep, ".")[:-3]
            self.load_extension(dot_path)

            logger.info(f"Loaded extension: {dot_path}")

    def run_bot(self) -> None:
        """Start bot."""
        super().run(constants.TOKEN)

    async def online_embed(self) -> None:
        """Send online embed."""
        embed = discord.Embed(title="Bot online", color=discord.Color.green())
        await self.log_channel.send(embed=embed)

    async def on_ready(self) -> None:
        """
        Send online embed and record start time.

        Raises:
            ValueError: log channel not found as text
        """
        logger.info("Bot online.")
        channel = self.get_channel(constants.LOG_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            raise ValueError("expected TextChannel but did not get one")

        self.log_channel = channel

        await self.online_embed()

        self.start_timestamp = time.time()

    async def close(self) -> None:
        """Close http session when bot is shuting down."""
        if self.http_session:
            await self.http_session.close()

        await super().close()

    async def on_error(self, event) -> None:  # type: ignore
        """
        Handle errors.

        Args:
            event: event that caused the error
        """
        (ty, er, tb) = sys.exc_info()
        string = f"{ty.__name__ if ty is not None else 'ERROR'}: {er}\n" + "".join(
            traceback.format_tb(tb)
        )

        logger.error(string)
        string = string[:1900]
        await self.log_channel.send(f"<@{constants.BOT_OWNER_ID}>\n```\n{string}```")


def run() -> None:
    """Start the bot."""
    bot = Bot()
    slash = discord_slash.SlashCommand(bot, sync_commands=True)  # noqa: F841
    bot.load_all_extensions()

    logger.info("Starting bot")
    bot.run_bot()

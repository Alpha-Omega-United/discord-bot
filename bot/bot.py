import os

import discord
from discord.ext import commands
import discord_slash
from loguru import logger

from bot import constants


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            # to be able to load cogs we need to use commands.Bot,
            # usally commands.bot operats on normal commands.
            # we are going to be using discord_slash we dont need a prefix
            # but since discord.py expects us to they require a prefix anyway
            # so just some spam is a nice work around
            command_prefix="sfsdknfsdoifmsoidoamdoadmoiadjmo",
            intents=discord.Intents.default(),
        )

    def load_all_extensions(self) -> None:
        for file in constants.Paths.cogs.glob("*.py"):
            dot_path = str(file).replace(os.sep, ".")[:-3]
            self.load_extension(dot_path)

            logger.info(f"Loaded extension: {dot_path}")

    def run(self) -> None:
        super().run(constants.TOKEN)

    async def on_ready(self):
        logger.info("Bot online.")


def run() -> None:
    bot = Bot()
    slash = discord_slash.SlashCommand(bot, sync_commands=True)  # noqa: F841
    bot.load_all_extensions()

    logger.info("Starting bot")
    bot.run()

import os
import sys

import discord
from discord.ext import commands
import discord_slash
from discord_slash import cog_ext

from bot.bot import Bot
from bot.constants import GUILD_ID


class InternalCog(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @cog_ext.cog_slash(
        name="status", description="Get info on bot", guild_ids=[GUILD_ID]
    )
    async def status_command(self, ctx: discord_slash.SlashContext) -> None:
        await ctx.defer()

        working_correctly = True

        self.bot.database["members"].find_one()

        fields = {
            "os": os.uname().release,
            "python": ".".join(map(str, sys.version_info)),
            "discord.py": discord.__version__,
            "discord-slash": discord_slash.__version__,
            "ping": f"{self.bot.latency * 1000:.0f} ms",
            "started": f"<t:{self.bot.start_timestamp:.0f}:R>",
        }
        embed = discord.Embed(
            color=discord.Color.green() if working_correctly else discord.Color.red(),
            title="Bot status",
        )
        for name, value in fields.items():
            embed.add_field(name=name, value=value)

        await ctx.send(embed=embed)


def setup(bot: Bot) -> None:
    bot.add_cog(InternalCog(bot))

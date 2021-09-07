"""Internal commnads."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import discord
import discord_slash
from discord.ext import commands
from discord_slash import cog_ext

from bot.constants import GUILD_ID

if TYPE_CHECKING:
    from bot.bot import Bot


class InternalCog(commands.Cog):
    """Internal commnads."""

    def __init__(self, bot: Bot):
        """
        Store bot value.

        Args:
            bot: bot this cog is a part of.
        """
        self.bot = bot

    @cog_ext.cog_slash(
        name="status", description="Get info on bot", guild_ids=[GUILD_ID]
    )
    async def status_command(self, ctx: discord_slash.SlashContext) -> None:
        """
        Display status for bot.

        Args:
            ctx: the interaction context
        """
        await ctx.defer()

        fields = {
            "os": os.uname().release,
            "python": ".".join(map(str, sys.version_info)),
            "discord.py": discord.__version__,
            "discord-slash": discord_slash.__version__,
            "ping": f"{self.bot.latency * 1000:.0f} ms",
            "started": f"<t:{self.bot.start_timestamp:.0f}:R>",
        }
        embed = discord.Embed(
            color=discord.Color.green(),
            title="Bot status",
        )
        for name, value in fields.items():
            embed.add_field(name=name, value=value)

        await ctx.send(embed=embed)


def setup(bot: Bot) -> None:
    """
    Add cog to bot.

    Args:
        bot: bot to add cog to
    """
    bot.add_cog(InternalCog(bot))

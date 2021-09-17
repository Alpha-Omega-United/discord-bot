"""Role info commnads."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from discord_slash import cog_ext
from discord_slash.utils import manage_commands
from loguru import logger

from bot.constants import GUILD_ID, HIDE_MESSAGES

if TYPE_CHECKING:
    from discord_slash.context import SlashContext

    from bot.bot import Bot


class RoleInfoCog(commands.Cog):
    """Role info commnads."""

    def __init__(self, bot: Bot):
        """
        Store bot value.

        Args:
            bot: bot this cog is a part of.
        """
        self.bot = bot
        self.role_info = self.bot.role_info

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Sync roles with db."""
        logger.info("syncing roles")
        for role in self.bot.guild.roles:
            color = role.color

            self.role_info.update_one(
                {"role_id": role.id},
                {
                    "$set": {
                        "name": role.name,
                        "color": {"r": color.r, "g": color.g, "b": color.b},
                    },
                    "$setOnInsert": {
                        "role_id": role.id,
                        "description": "No description provided yet.",
                    },
                },
                upsert=True,
            )
        logger.info("synced roles")

    @cog_ext.cog_slash(
        name="role",
        description="Get description of roles",
        options=[
            manage_commands.create_option(
                name="role",
                description="role to get description of.",
                option_type=manage_commands.SlashCommandOptionType.ROLE,
                required=True,
            )
        ],
        guild_ids=[GUILD_ID],
    )
    async def role_command(self, ctx: SlashContext, role: discord.Role) -> None:
        """
        Display description of roles.

        Args:
            ctx: slash context
            role: role to get description of
        """
        role_data = self.role_info.find_one({"role_id": role.id})

        if role_data is None:
            # something has gone wrong!
            logger.error("role info returned None!")
            await ctx.send(
                "Sorry there was an unexpected error processing your request.",
                hidden=HIDE_MESSAGES,
            )
            return

        name = role.name
        color = role.color
        description: str = role_data["description"]

        embed = discord.Embed(title=name, color=color, description=description)

        await ctx.send(embed=embed, hidden=HIDE_MESSAGES)


def setup(bot: Bot) -> None:
    """
    Add cog to bot.

    Args:
        bot: bot to add cog to
    """
    bot.add_cog(RoleInfoCog(bot))

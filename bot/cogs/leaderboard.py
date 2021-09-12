"""Manage the servers leaderboard."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import discord
import pymongo
from discord.ext import commands, tasks

from bot import constants

if TYPE_CHECKING:
    from bot.bot import Bot
    from bot.types import MemberData

AMOUNT_OF_USERS = 10


class LeaderboardCog(commands.Cog):
    """Manage the servers leaderboard."""

    def __init__(self, bot: Bot):
        """
        Set required values.

        Args:
            bot: the bot this cog is a part of
        """
        self.bot = bot
        self.members = bot.members

        self.leaderboard_message: discord.Message

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """
        Create/get first message and timer.

        Raises:
            ValueError: channel not found
            TypeError: channel not of correct type
        """
        # get first message
        channel = self.bot.get_channel(constants.LEADERBOARD_CHANNEL_ID)

        if channel is None:
            raise ValueError(f"could not find channel {channel}")

        if not isinstance(channel, discord.TextChannel):
            raise TypeError(f"incorrect channel type {channel}")

        if channel.last_message_id is not None:
            self.leaderboard_message = await channel.fetch_message(
                channel.last_message_id
            )
        else:
            self.leaderboard_message = await channel.send("TMP")

        self.update_leaderboard.start()

    @tasks.loop(minutes=10)
    async def update_leaderboard(self) -> None:
        """Update the leaderboard message with the newest points."""
        current_time = time.time()
        top_users = (
            self.members.find()
            .sort("points", pymongo.DESCENDING)
            .limit(AMOUNT_OF_USERS)
        )

        description_lines = []

        user: MemberData
        for user in top_users:
            twitch_channel_name = user["twitch_name"]
            twitch_mention = (
                f"[{twitch_channel_name}](https://www.twitch.tv/{twitch_channel_name})"
            )

            if "discord_id" in user and user["discord_id"] is not None:
                user_mention = f"<@{user['discord_id']}> / {twitch_mention}"
            else:
                user_mention = twitch_mention

            description_lines.append(f"{user_mention} : **{user['points']}**")

        embed = discord.Embed(
            title=f"last updated <t:{current_time:.0f}:R>",
            color=discord.Color.green(),
            description="\n".join(description_lines),
        )

        await self.leaderboard_message.edit(content="", embed=embed)


def setup(bot: Bot) -> None:
    """
    Add cog to bot.

    Args:
        bot: bot to add cog to
    """
    bot.add_cog(LeaderboardCog(bot))

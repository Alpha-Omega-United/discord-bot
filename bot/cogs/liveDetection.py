"""Manages live detectoion."""


from typing import Optional

import discord
from discord.ext import commands
from loguru import logger

from bot import constants
from bot.bot import Bot


class LiveCog(commands.Cog):
    """Manages live detectoion."""

    def __init__(self, bot: Bot):
        """
        Set required values.

        Args:
            bot: the bot this cog is a part of
        """
        self.bot = bot
        self.members = self.bot.database["members"]

    @staticmethod
    def user_is_streaming(user: discord.Member) -> Optional[discord.Streaming]:
        """
        Check if a user is streaming and return activity.

        Args:
            user: user to check

        Returns:
            returns activity if found
        """
        for activity in user.activities:
            if isinstance(activity, discord.Streaming):
                return activity

        return None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """
        Sync live users.

        Raises:
            TypeError: guild not found
        """
        logger.info("syncing live")

        guild = self.bot.get_guild(constants.GUILD_ID)

        if guild is None:
            raise TypeError("error getting guild")

        for user in guild.members:
            streaming_act = self.user_is_streaming(user)

            if streaming_act is None:
                self.members.update_one(
                    {"discord_id": str(user.id)},
                    {"$set": {"stream": None}},
                )
            else:
                self.members.update_one(
                    {"discord_id": str(user.id)},
                    {
                        "$set": {
                            "stream": {
                                "live_where": streaming_act.platform.lower(),
                                "live_url": streaming_act.url,
                            }
                        }
                    },
                )

        logger.info("synced live.")

    @commands.Cog.listener()
    async def on_member_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        """
        Detect live status changes.

        Args:
            before: state of user before update
            after: state of user after update
        """
        was_streaming = self.user_is_streaming(before) is not None
        streaming_act = self.user_is_streaming(after)
        is_streaming = streaming_act is not None

        if was_streaming != is_streaming:
            logger.info(f"updating live status for {before} to {is_streaming}")
            if streaming_act is None:
                self.members.update_one(
                    {"discord_id": str(after.id)},
                    {"$set": {"stream": None}},
                )
            else:
                self.members.update_one(
                    {"discord_id": str(after.id)},
                    {
                        "$set": {
                            "stream": {
                                "live_where": streaming_act.platform.lower(),
                                "live_url": streaming_act.url,
                            }
                        }
                    },
                )


def setup(bot: Bot) -> None:
    """
    Add cog to bot.

    Args:
        bot: bot to add cog to
    """
    bot.add_cog(LiveCog(bot))

from typing import Optional
import discord
from discord.ext import commands
from loguru import logger

from bot.bot import Bot
from bot import constants


class LiveCog(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.members = self.bot.database["members"]

    @staticmethod
    def user_is_streaming(user: discord.Member) -> Optional[discord.Streaming]:
        for activity in user.activities:
            if activity.type == discord.ActivityType.streaming:
                return activity

        return None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        logger.info("syncing live")

        for user in self.bot.get_guild(constants.GUILD_ID).members:
            streamingAct = self.user_is_streaming(user)

            logger.info(
                f"updating live status for {user} to {streamingAct is not None}"
            )
            if streamingAct is None:
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
                                "live_where": streamingAct.platform.lower(),
                                "live_url": streamingAct.url,
                            }
                        }
                    },
                )

        logger.info("synced live.")

    @commands.Cog.listener()
    async def on_member_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        wasStreaming = self.user_is_streaming(before) is not None
        streamingAct = self.user_is_streaming(after)
        isStreaming = streamingAct is not None

        if wasStreaming != isStreaming:
            logger.info(f"updating live status for {before} to {isStreaming}")
            if streamingAct is None:
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
                                "live_where": streamingAct.platform.lower(),
                                "live_url": streamingAct.url,
                            }
                        }
                    },
                )


def setup(bot: Bot) -> None:
    bot.add_cog(LiveCog(bot))

import asyncio
import time
import discord
from discord.ext import commands
import pymongo

from bot.bot import Bot
from bot import constants


SLEEP_TIME = 60 * 10  # 10 minutes
AMOUNT_OF_USERS = 10


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.members = self.bot.database["members"]

        self.leaderboard_message: discord.Message = None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        # get first message
        channel = self.bot.get_channel(constants.LEADERBOARD_CHANNEL_ID)

        if channel.last_message_id is not None:
            self.leaderboard_message = await channel.fetch_message(
                channel.last_message_id
            )
        else:
            self.leaderboard_message = await channel.send("TMP")

        while True:
            await self.update_leaderboard()
            await asyncio.sleep(SLEEP_TIME)

    async def update_leaderboard(self) -> None:
        current_time = time.time()
        topUsers = (
            self.members.find()
            .sort("points", pymongo.DESCENDING)
            .limit(AMOUNT_OF_USERS)
        )

        description_lines = []
        for user in topUsers:
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
    bot.add_cog(LeaderboardCog(bot))

"""Detecting inactive users."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional, cast

import discord
from discord.ext import commands, tasks
from loguru import logger

from bot.constants import GUILD_ID

if TYPE_CHECKING:
    from typing import Dict

    from bot.bot import Bot


PRUNE_DAYS = 1


class InactiveCog(commands.Cog):
    """Detecting inactive users."""

    guild: discord.Guild

    def __init__(self, bot: Bot):
        """
        Store bot value.

        Args:
            bot: bot this cog is a part of.
        """
        self.bot = bot
        self.last_seen_db = self.bot.database["last_seen"]

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """
        Fetch needed values.

        Raises:
            ValueError: guild not found
        """
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            raise ValueError("Guild not found.")
        self.guild = guild

        # sync members
        logger.info("syncing inactive members.")

        members: Dict[discord.Member, Optional[datetime]] = {
            member: None for member in self.guild.members if not member.bot
        }
        thirty_days_ago = datetime.today() - timedelta(days=30)

        for channel in self.guild.channels:
            if isinstance(channel, discord.TextChannel):
                logger.info(f"getting messages in {channel}")
                async for message in channel.history(limit=None, after=thirty_days_ago):
                    logger.debug(f"{message.author}: {message.content}")
                    author = cast(Optional[discord.Member], message.author)
                    if author in members and members[author] is None:
                        members[author] = message.edited_at or message.created_at

        for member, last_seen in members.items():
            logger.info(f"updating for user {member} to {last_seen}")
            self.last_seen_db.update_one(
                {"discord_id": member.id},
                {
                    "$set": {
                        "last_seen": last_seen
                        if last_seen is not None
                        else datetime.fromtimestamp(0),
                    },
                    "$setOnInsert": {
                        "discord_id": member.id,
                        "sent_notification": False,
                    },
                },
                upsert=True,
            )

        logger.info("synced inactive members.")

        self.check_inactivty_statuses.start()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Store new last_seen time on message.

        Args:
            message: message that was sent
        """
        if message.author.bot:
            return

        self.last_seen_db.update_one(
            {"discord_id": message.author.id},
            {
                "$currentDate": {"last_seen": True},
                "$set": {"sent_notification": False},
            },
        )

    @tasks.loop(hours=1)
    async def check_inactivty_statuses(self) -> None:
        """Do inactive user checks."""
        logger.info("doing inactivty check")

        await self.send_inactive_notifications()
        await self.kick_inactive_users()

        logger.info("inactivty check done")

    async def send_inactive_notifications(self) -> None:
        """Check db for who needs to be notified."""
        logger.info("checking for users to notoify")
        need_to_be_notified = list(
            self.last_seen_db.find(
                {
                    "last_seen": {"$lte": datetime.today() - timedelta(days=7)},
                    "sent_notification": False,
                }
            )
        )

        for member_data in need_to_be_notified:
            member = self.guild.get_member(member_data["discord_id"])
            if member is None:
                logger.error(f"could not get member for id {member_data}")
                continue

            if member.bot:
                continue

            logger.info(f"notifiying member {member}")

            last_seen: datetime = member_data["last_seen"]

            when_they_will_be_kicked = last_seen + timedelta(days=30)
            timestamp_they_will_be_kicked = (
                f"<t:{when_they_will_be_kicked.timestamp():.0f}>"
            )

            notify_embed = discord.Embed(
                color=discord.Color.red(),
                title="WARNING: you might get kicked.",
                description=(
                    "you have not been active in over 7 days,"
                    f"you will be kicked from the server at {timestamp_they_will_be_kicked}"
                ),
            )

            notify_embed.set_thumbnail(url=self.guild.icon_url)  # type: ignore

            try:
                await member.send(embed=notify_embed)
            except discord.Forbidden:
                logger.error("could not notify user.")
            else:
                logger.info("notifed user.")

        self.last_seen_db.update_many(
            {"_id": {"$in": [data["_id"] for data in need_to_be_notified]}},
            {"$set": {"sent_notification": True}},
        )

    async def kick_inactive_users(self) -> None:
        """Kick members being inactive for over 30 days."""
        logger.info("checking for users to kick")
        need_to_be_kicked = list(
            self.last_seen_db.find(
                {
                    "last_seen": {"$lte": datetime.today() - timedelta(days=30)},
                }
            )
        )

        for member_data in need_to_be_kicked:
            member = self.guild.get_member(member_data["discord_id"])
            if member is None:
                logger.error(f"could not get member for id {member_data}")
                continue

            if member.bot:
                continue

            logger.info(f"kicking member {member}")

            notify_embed = discord.Embed(
                color=discord.Color.red(),
                title="KICKED: you have been kicked for inactivty.",
                description=(
                    "you have not been active in over 30 days, "
                    "you have been kicked from AoU, but you can rejoin!"
                ),
            )

            notify_embed.set_thumbnail(url=self.guild.icon_url)  # type: ignore

            invite = await self.guild.text_channels[0].create_invite(unique=False)

            try:
                await member.send(invite.url, embed=notify_embed)
            except discord.Forbidden:
                logger.error("could not notify user.")
            else:
                logger.info("notifed user.")

            try:
                await member.kick(reason="inactive for 30 days.")
            except discord.Forbidden:
                logger.error("could not kick user.")
            else:
                logger.info("kick user.")


def setup(bot: Bot) -> None:
    """
    Add cog to bot.

    Args:
        bot: bot to add cog to
    """
    bot.add_cog(InactiveCog(bot))

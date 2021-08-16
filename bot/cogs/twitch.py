import re

from typing import Optional, TypedDict
import discord

from discord.ext import commands
from discord_slash import cog_ext, SlashContext, manage_commands, manage_components
import discord_slash
from discord_slash.context import InteractionContext
from discord_slash.model import SlashCommandOptionType
from loguru import logger
from bot import constants

from bot.constants import GUILD_ID
from bot.bot import Bot

# matches:
# https://twitch.tv/username
# http://twitch.tv/username
# twitch.tv/username
# (if this does not match we assume it is just a normal username)
TWITCH_URL = re.compile(r"^(https?:\/\/)?twitch\.tv\/(.+)$")

TWITCH_TOKEN_ENDPOINT = "https://id.twitch.tv/oauth2/token"
TWITCH_USER_ENDPOINT = "https://api.twitch.tv/helix/users"


class LinkedData(TypedDict):
    discord_name: str
    discord_id: int
    twitch_name: str
    twitch_id: int


class Twitch(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.linked_accounts = bot.database["members"]
        self.token = None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Get twitch token."""
        params = {
            "client_id": constants.TWITCH_CLIENT_ID,
            "client_secret": constants.TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials",
        }

        logger.info("Grabbing twitch token.")
        async with self.bot.http_session.post(
            TWITCH_TOKEN_ENDPOINT, params=params
        ) as resp:
            data = await resp.json()

        # ! we dont really handle expiry,
        # ! but I have a feeling the bot will be restarting often enough for that not to be needed.
        self.token = data["access_token"]
        logger.info("Got twitch token.")

    async def get_twithc_id(self, twitch_name: str) -> Optional[int]:
        """Conntact twitch about their id and to make sure they exsist."""
        logger.info(f"getting twitch_id for {twitch_name!r}")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Client-Id": constants.TWITCH_CLIENT_ID,
        }
        params = {"login": twitch_name}

        async with self.bot.http_session.get(
            TWITCH_USER_ENDPOINT, params=params, headers=headers
        ) as resp:
            data = await resp.json()

        data = data["data"]
        if len(data) == 0:
            id_ = None
        else:
            id_ = int(data[0]["id"])

        logger.info(f"id got -> {id_}")

        return id_

    def insert_new_link(self, data: LinkedData) -> None:
        self.linked_accounts.insert_one(data)

    def update_data(self, id_: str, newData: LinkedData) -> bool:
        """Update the document with new data.

        return: if a update took place or not.
        """
        logger.info(f"performing update with: {newData}")

        updateInfo = self.linked_accounts.replace_one({"_id": id_}, newData)

        return updateInfo.modified_count >= 1

    def delete_data(self, id_: int) -> None:
        logger.info(f"deleting documents matching {id_}")

        deleteInfo = self.linked_accounts.delete_one({"_id": id_})

        return deleteInfo.deleted_count >= 1

    def search_for_both(self, discord_id: int, twitch_id: int) -> Optional[LinkedData]:
        """Searches the db for documents that matches the discord_id OR the twitch_id

        in the code we are going to be searching for both of these, so grouping them in one operation is best.
        """

        return self.linked_accounts.find_one(
            {"$or": [{"discord_id": discord_id}, {"twitch_id": twitch_id}]}
        )

    def search_for_discord(self, discord_id: int) -> Optional[LinkedData]:
        """Searches the db for documents that matches the discord_id"""

        return self.linked_accounts.find_one({"discord_id": discord_id})

    @cog_ext.cog_subcommand(
        base="twitch",
        base_description="Commands related to twich.",
        name="register",
        description="register a link between this discord account and your twitch name in our system.",
        options=[
            manage_commands.create_option(
                name="twitch_name",
                description="Your twitch user name",
                option_type=SlashCommandOptionType.STRING,
                required=True,
            )
        ],
        guild_ids=[GUILD_ID],
    )
    async def register_command(self, ctx: SlashContext, twitch_name: str) -> None:
        await ctx.defer(hidden=constants.HIDE_MESSAGES)

        # detect if it a url
        match = TWITCH_URL.fullmatch(twitch_name)
        if match:
            twitch_name = match.groups()[1]

        twitch_id = await self.get_twithc_id(twitch_name)

        if twitch_id is None:
            await ctx.send(
                f"Sorry we could not find the twitch user `{twitch_name}`",
                hidden=constants.HIDE_MESSAGES,
            )
            return

        discord_name = f"{ctx.author.name}#{ctx.author.discriminator}"
        discord_id = ctx.author.id

        alreadyExsisting = self.search_for_both(discord_id, twitch_id)
        updating = False
        if alreadyExsisting is not None:
            logger.info(f"duplicate found: {alreadyExsisting}")
            # okay let's handle this!
            if alreadyExsisting["discord_id"] == discord_id:
                # okay it is just he same user, let's update stuff
                updating = True
            else:  # We know then it is because the twitch ids matched
                if (
                    alreadyExsisting.get("discord_id", None) is None
                    or alreadyExsisting["discord_id"] == ""
                ):
                    updating = True
                else:
                    alreadyOwningUser = self.bot.get_user(
                        alreadyExsisting["discord_id"]
                    )
                    if alreadyOwningUser is not None:
                        user_msg_part = alreadyOwningUser.mention
                    else:
                        user_msg_part = f"`{alreadyExsisting['discord_name']}`"

                    await ctx.send(
                        f"We are sorry to inform you that {user_msg_part} "
                        f"has already registerd that twitch name (`{twitch_name}`)",
                        hidden=constants.HIDE_MESSAGES,
                    )
                    return

        data: LinkedData = {
            "discord_name": discord_name,
            "discord_id": discord_id,
            "twitch_name": twitch_name,
            "twitch_id": twitch_id,
            "points": 0,
            "isAdmin": any(
                role.id == constants.ADMIN_ROLE_ID for role in ctx.author.roles
            ),
        }

        if updating:
            self.update_data(alreadyExsisting["_id"], data)
            await ctx.send(
                f"We have registerd a link between `{twitch_name}` and `{discord_name}` \n"
                f"_**UPDATE: **_ this operation overwrote a previously registerd twitch name,"
                + f"`{alreadyExsisting['twitch_name']}`",
                hidden=constants.HIDE_MESSAGES,
            )
        else:
            self.insert_new_link(data)
            await ctx.send(
                f"We have registerd a link between `{twitch_name}` and `{discord_name}`",
                hidden=constants.HIDE_MESSAGES,
            )

        logger.info(f"Registerd link {discord_name} -> {twitch_name}")

    def format_data_for_discord(self, data: LinkedData) -> discord.Embed:
        embed = discord.Embed(title=f"Data for user `{data['discord_name']}`")

        for name, value in data.items():
            if name in {"_id", "roles"}:
                continue

            embed.add_field(name=name, value=str(value), inline=False)

        return embed

    async def delete_popup(self, ctx: SlashContext, data: LinkedData) -> None:
        embed = self.format_data_for_discord(data)

        are_you_sure = manage_components.create_button(
            style=manage_components.ButtonStyle.danger,
            label="delete",
            emoji="🗑️",
        )
        cancel = manage_components.create_button(
            style=manage_components.ButtonStyle.primary, label="CANCEL", emoji="⛔"
        )

        row = manage_components.create_actionrow(cancel, are_you_sure)

        await ctx.send(
            "Do you really want to delete this account link?",
            embed=embed,
            components=[row],
            hidden=constants.HIDE_MESSAGES,
        )

        int_ctx: InteractionContext = await manage_components.wait_for_component(
            self.bot, None, row
        )

        if int_ctx.custom_id == cancel["custom_id"]:
            await int_ctx.edit_origin(content="CANCELD", embed=None, components=None)
        elif int_ctx.custom_id == are_you_sure["custom_id"]:
            self.delete_data(data["_id"])
            await int_ctx.edit_origin(
                content=f"Deleted data for <@{data['discord_id']}>",
                embed=None,
                components=None,
            )

    @cog_ext.cog_subcommand(
        base="twitch",
        name="unregister",
        description="remove your discord -> twitch link from our systems.",
        guild_ids=[GUILD_ID],
    )
    async def unregister(self, ctx: SlashContext) -> None:
        await ctx.defer(hidden=constants.HIDE_MESSAGES)
        data = self.search_for_discord(ctx.author.id)

        if data is None:
            await ctx.send(
                "Sorry we could not find you in our database",
                hidden=constants.HIDE_MESSAGES,
            )
        else:
            await self.delete_popup(ctx, data)

    @cog_ext.cog_subcommand(
        base="admin",
        name="delete_twitch",
        description="delete somebody elses database entry.",
        options=[
            manage_commands.create_option(
                name="user",
                description="the user to delete the entry of",
                option_type=SlashCommandOptionType.USER,
                required=True,
            )
        ],
        guild_ids=[GUILD_ID],
        base_default_permission=False,
        base_permissions={
            GUILD_ID: [
                manage_commands.create_permission(
                    id=constants.ADMIN_ROLE_ID,
                    id_type=discord_slash.model.SlashCommandPermissionType.ROLE,
                    permission=True,
                )
            ]
        },
    )
    async def delete_command(self, ctx: SlashContext, user: discord.User) -> None:
        await ctx.defer(hidden=constants.HIDE_MESSAGES)
        data = self.search_for_discord(user.id)
        if data is None:
            await ctx.send("this user is not registerd", hidden=constants.HIDE_MESSAGES)
        else:
            await self.delete_popup(ctx, data)


def setup(bot: Bot) -> None:
    bot.add_cog(Twitch(bot))

import re
import asyncio

from typing import Any, Dict, Optional
import discord

from discord.ext import commands
from discord_slash import (
    cog_ext,
    SlashContext,
    manage_commands,
    manage_components,
)
import discord_slash
from discord_slash.model import SlashCommandOptionType
from loguru import logger
from bot import constants

from bot.constants import GUILD_ID
from bot.bot import Bot
from bot.paginator import EmbedPaginator

# matches:
# https://twitch.tv/username
# http://twitch.tv/username
# twitch.tv/username
# (if this does not match we assume it is just a normal username)
TWITCH_URL = re.compile(r"^(https?:\/\/)?twitch\.tv\/(.+)$")

TWITCH_TOKEN_ENDPOINT = "https://id.twitch.tv/oauth2/token"
TWITCH_USER_ENDPOINT = "https://api.twitch.tv/helix/users"


class Twitch(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.members = bot.database["members"]
        self.token = None

    async def sync_admins(self) -> None:
        logger.info("syncing admins")
        admins = [
            str(member.id)
            for member in self.bot.get_guild(GUILD_ID).members
            if any(role.id == constants.ADMIN_ROLE_ID for role in member.roles)
        ]

        self.members.update_many(
            {"discord_id": {"$in": admins}}, {"$set": {"isAdmin": True}}
        )
        self.members.update_many(
            {"discord_id": {"$not": {"$in": admins}}}, {"$set": {"isAdmin": False}}
        )

        logger.info("synced admins.")

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

        await self.sync_admins()

    async def get_twithc_data(self, twitch_name: str) -> Optional[Dict[str, Any]]:
        """Conntact twitch about their id and to make sure they exsist."""
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
            user_data = None
        else:
            user_data = data[0]
            user_data["id"] = int(user_data["id"])

        return user_data

    @cog_ext.cog_subcommand(
        base="twitch",
        base_description="Commands related to twich.",
        name="register",
        description="register a link between this discord account and your twitch account.",
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
        logger.info(f"registering {twitch_name} for {ctx.author}")
        await ctx.defer(hidden=constants.HIDE_MESSAGES)

        # detect if it a url
        match = TWITCH_URL.fullmatch(twitch_name)
        if match:
            twitch_name = match.groups()[1]

        twitch_data = await self.get_twithc_data(twitch_name)
        if twitch_data is None:
            error_embed = discord.Embed(
                color=discord.Color.red(),
                title="Cant not find account.",
                description=(
                    f"Could not find twitch account with name `{twitch_name}`"
                ),
            )
            await ctx.send(embed=error_embed, hidden=constants.HIDE_MESSAGES)
            return

        duplicateTwitchDocument = self.members.find_one(
            {"twitch_id": twitch_data["id"]},
        )
        if duplicateTwitchDocument is not None:
            if duplicateTwitchDocument.get("discord_id", None) is None:
                await self.link_twitch(ctx, duplicateTwitchDocument, twitch_data)
                return

            logger.info("already owned twitch account.")
            mention = f"<@{duplicateTwitchDocument['discord_id']}>"

            error_embed = discord.Embed(
                color=discord.Color.red(),
                title="already registerd by somebody else.",
                description=(
                    f"{mention} has already registerd [{twitch_name}](https://twitch.tv/{twitch_data['login']}), "
                    "if they are not the owner of this account please contact an admin"
                ),
            )
            error_embed.set_thumbnail(url=twitch_data["profile_image_url"])

            await ctx.send(embed=error_embed, hidden=constants.HIDE_MESSAGES)
            return

        duplicateDiscordDocuemnt = self.members.find_one(
            {"discord_id": str(ctx.author.id)}
        )
        if duplicateDiscordDocuemnt is None:
            await self.register_new(ctx, twitch_data)
        else:
            await self.update_twitch(ctx, duplicateDiscordDocuemnt, twitch_data)

    async def register_new(
        self, ctx: SlashContext, twitch_data: Dict[str, Any]
    ) -> None:
        conformation_embed = discord.Embed(
            color=discord.Color.blue(),
            title=f"Register {twitch_data['login']}",
            description=(
                "you are about to register a link between this discord account and "
                f"[{twitch_data['login']}](https://twitch.tv/{twitch_data['login']}) "
                "make sure this is what you are meaning to do!"
            ),
        )
        conformation_embed.set_thumbnail(url=twitch_data["profile_image_url"])
        conformation_embed.set_footer(
            text="You can change this latter using /twitch register"
        )

        confirm_button = manage_components.create_button(
            style=manage_components.ButtonStyle.green, label="confirm", emoji="☑️"
        )
        cancel_button = manage_components.create_button(
            style=manage_components.ButtonStyle.red, label="cancel", emoji="⛔"
        )

        row = manage_components.create_actionrow(confirm_button, cancel_button)

        await ctx.send(
            embed=conformation_embed, components=[row], hidden=constants.HIDE_MESSAGES
        )

        button_ctx = await manage_components.wait_for_component(
            self.bot, components=row
        )

        confirm_button["disabled"] = True
        cancel_button["disabled"] = True
        row = manage_components.create_actionrow(confirm_button, cancel_button)

        if button_ctx.custom_id == cancel_button["custom_id"]:
            conformation_embed.color = discord.Color.red()
            conformation_embed.title += ": **CANCELD**"

            logger.info("canceld by user.")
            await button_ctx.edit_origin(embed=conformation_embed, components=[row])

        else:  # we assume we dont have other buttons
            conformation_embed.color = discord.Color.green()
            conformation_embed.title += ": **COMPLETED**"

            data = {
                "twitch_name": twitch_data["login"].lower(),
                "twitch_id": twitch_data["id"],
                "discord_name": f"{ctx.author.name}#{ctx.author.discriminator}",
                "discord_id": str(ctx.author.id),
                "points": 0,
                "isAdmin": any(
                    role.id == constants.ADMIN_ROLE_ID for role in ctx.author.roles
                ),
            }
            self.members.insert_one(data)

            await button_ctx.edit_origin(embed=conformation_embed, components=[row])

    async def update_twitch(self, ctx: SlashContext, duplicate, twitch_data) -> None:
        conformation_embed = discord.Embed(
            color=discord.Color.blue(),
            title=f"Overwrite {duplicate['twitch_name']} with {twitch_data['login']}",
            description=(
                "you are about to register a link between this discord account and "
                f"[{twitch_data['login']}](https://twitch.tv/{twitch_data['login']}) "
                "but you have already registerd"
                f"[{duplicate['twitch_name']}](https://twitch.tv/{duplicate['twitch_name']}) "
                "this will overwrite that "
                "make sure this is what you are meaning to do!"
                "\n\n**WARNING:** this will reset your points!"
            ),
        )
        conformation_embed.set_thumbnail(url=twitch_data["profile_image_url"])

        confirm_button = manage_components.create_button(
            style=manage_components.ButtonStyle.red, label="confirm", emoji="☑️"
        )
        cancel_button = manage_components.create_button(
            style=manage_components.ButtonStyle.blue, label="cancel", emoji="⛔"
        )

        row = manage_components.create_actionrow(confirm_button, cancel_button)

        await ctx.send(
            embed=conformation_embed, components=[row], hidden=constants.HIDE_MESSAGES
        )

        button_ctx = await manage_components.wait_for_component(
            self.bot, components=row
        )

        confirm_button["disabled"] = True
        cancel_button["disabled"] = True
        row = manage_components.create_actionrow(confirm_button, cancel_button)

        if button_ctx.custom_id == cancel_button["custom_id"]:
            conformation_embed.color = discord.Color.red()
            conformation_embed.title += ": **CANCELD**"

            await button_ctx.edit_origin(embed=conformation_embed, components=[row])

        else:  # we assume we dont have other buttons
            conformation_embed.color = discord.Color.green()
            conformation_embed.title += ": **COMPLETED**"

            data = {
                "twitch_name": twitch_data["login"].lower(),
                "twitch_id": twitch_data["id"],
                "points": 0,
            }
            self.members.update_one({"_id": duplicate["_id"]}, {"$set": data})

            await button_ctx.edit_origin(embed=conformation_embed, components=[row])

    async def link_twitch(self, ctx: SlashContext, duplicate, twitch_data) -> None:
        conformation_embed = discord.Embed(
            color=discord.Color.blue(),
            title=f"Register {twitch_data['login']}",
            description=(
                "you are about to register a link between this discord account and "
                f"[{twitch_data['login']}](https://twitch.tv/{twitch_data['login']}) "
                "make sure this is what you are meaning to do!"
                "\n\n**NOTE:** you were already registerd, but a discord account was missing."
            ),
        )
        conformation_embed.set_thumbnail(url=twitch_data["profile_image_url"])

        confirm_button = manage_components.create_button(
            style=manage_components.ButtonStyle.green, label="confirm", emoji="☑️"
        )
        cancel_button = manage_components.create_button(
            style=manage_components.ButtonStyle.red, label="cancel", emoji="⛔"
        )

        row = manage_components.create_actionrow(confirm_button, cancel_button)

        await ctx.send(
            embed=conformation_embed, components=[row], hidden=constants.HIDE_MESSAGES
        )

        button_ctx = await manage_components.wait_for_component(
            self.bot, components=row
        )

        confirm_button["disabled"] = True
        cancel_button["disabled"] = True
        row = manage_components.create_actionrow(confirm_button, cancel_button)

        if button_ctx.custom_id == cancel_button["custom_id"]:
            conformation_embed.color = discord.Color.red()
            conformation_embed.title += ": **CANCELD**"

            await button_ctx.edit_origin(embed=conformation_embed, components=[row])

        else:  # we assume we dont have other buttons
            conformation_embed.color = discord.Color.green()
            conformation_embed.title += ": **COMPLETED**"

            data = {
                "discord_name": f"{ctx.author.name}#{ctx.author.discriminator}",
                "discord_id": str(ctx.author.id),
            }
            self.members.update_one({"_id": duplicate["_id"]}, {"$set": data})

            await button_ctx.edit_origin(embed=conformation_embed, components=[row])

    def format_data_for_discord(self, data) -> discord.Embed:
        embed = discord.Embed(title=f"Data for user `{data['discord_name']}`")

        for name, value in data.items():
            if name in {"_id", "twitch_id", "discord_id", "stream"}:
                continue

            if value is not None and value != "":
                embed.add_field(name=name, value=str(value))  # , inline=False)

        return embed

    async def delete_popup(self, ctx: SlashContext, data) -> None:
        embed = self.format_data_for_discord(data)
        embed.colour = discord.Color.blue()
        embed.title = f"Delete `{data['discord_name']}`/`{data['twitch_name']}`"

        are_you_sure = manage_components.create_button(
            style=manage_components.ButtonStyle.danger,
            label="delete",
            emoji="🗑️",
        )
        cancel = manage_components.create_button(
            style=manage_components.ButtonStyle.primary, label="cancel", emoji="⛔"
        )

        row = manage_components.create_actionrow(cancel, are_you_sure)

        await ctx.send(
            "Do you really want to delete this account?",
            embed=embed,
            components=[row],
            hidden=constants.HIDE_MESSAGES,
        )

        int_ctx = await manage_components.wait_for_component(self.bot, components=row)

        are_you_sure["disabled"] = True
        cancel["disabled"] = True
        row = manage_components.create_actionrow(are_you_sure, cancel)

        if int_ctx.custom_id == cancel["custom_id"]:
            embed.color = discord.Color.green()
            embed.title += ": **CANCELD**"

            await int_ctx.edit_origin(embed=embed, components=[row])
        elif int_ctx.custom_id == are_you_sure["custom_id"]:
            embed.color = discord.Color.red()
            embed.title += ": **DELETED**"

            self.members.delete_one({"_id": data["_id"]})
            await int_ctx.edit_origin(embed=embed, components=[row])

    @cog_ext.cog_subcommand(
        base="twitch",
        name="unregister",
        description="remove your discord -> twitch link from our systems.",
        guild_ids=[GUILD_ID],
    )
    async def unregister(self, ctx: SlashContext) -> None:
        await ctx.defer(hidden=constants.HIDE_MESSAGES)
        data = self.members.find_one({"discord_id": str(ctx.author.id)})

        if data is None:
            error_embed = discord.Embed(
                color=discord.Color.red(),
                title="Not found.",
                description="We could not find an account connected to this discord account.",
            )
            await ctx.send(
                embed=error_embed,
                hidden=constants.HIDE_MESSAGES,
            )
        else:
            await self.delete_popup(ctx, data)

    @cog_ext.cog_subcommand(
        base="twitch",
        name="points",
        description="check your points",
        options=[],
        guild_ids=[GUILD_ID],
    )
    async def points_command(self, ctx: SlashContext) -> None:
        await ctx.defer(hidden=constants.HIDE_MESSAGES)
        userData = self.members.find_one({"discord_id": str(ctx.author.id)})
        if userData is None:
            error_embed = discord.Embed(
                color=discord.Color.red(),
                title="Not found.",
                description=(
                    "We could not find an account connected to this discord account.\n"
                    "you can register one using `/twitch register <your_twitch_name>`"
                ),
            )
            await ctx.send(
                embed=error_embed,
                hidden=constants.HIDE_MESSAGES,
            )
        else:
            points = userData["points"]
            points_embed = discord.Embed(
                color=discord.Color.blue(),
                title=f"Points for {userData['twitch_name']}",
                description=f"You have **{points}** points",
            )

            await ctx.send(embed=points_embed, hidden=constants.HIDE_MESSAGES)

    @cog_ext.cog_subcommand(
        base="admin",
        name="delete",
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
        data = self.members.find_one({"discord_id": str(user.id)})
        if data is None:
            error_embed = discord.Embed(
                color=discord.Color.red(),
                title="Not found.",
                description="We could not find an account connected to this discord account.",
            )
            await ctx.send(
                embed=error_embed,
                hidden=constants.HIDE_MESSAGES,
            )
        else:
            await self.delete_popup(ctx, data)

    @cog_ext.cog_subcommand(
        base="admin",
        name="view_all",
        description="view all database entries.",
        options=[],
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
    async def view_all_command(self, ctx: SlashContext) -> None:
        await ctx.defer(hidden=constants.HIDE_MESSAGES)
        embeds = [
            self.format_data_for_discord(account) for account in self.members.find()
        ]
        paginator = EmbedPaginator(embeds, "User: ")
        asyncio.create_task(paginator.start(self.bot, ctx, hidden=False))

    @cog_ext.cog_subcommand(
        base="admin",
        name="transfer",
        description="transfer somebodys twitch name to another discord account.",
        options=[
            manage_commands.create_option(
                name="from_user",
                description="the user to transfer from",
                option_type=SlashCommandOptionType.USER,
                required=True,
            ),
            manage_commands.create_option(
                name="to_user",
                description="the user to transfer to",
                option_type=SlashCommandOptionType.USER,
                required=True,
            ),
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
    async def transfer_command(
        self, ctx: SlashContext, from_user: discord.User, to_user: discord.User
    ) -> None:
        await ctx.defer(hidden=constants.HIDE_MESSAGES)
        data = self.members.find_one({"discord_id": str(from_user.id)})
        if data is None:
            error_embed = discord.Embed(
                color=discord.Color.red(),
                title="Not found.",
                description="We could not find an account connected to this discord account.",
            )
            await ctx.send(
                embed=error_embed,
                hidden=constants.HIDE_MESSAGES,
            )
            return

        conformation_embed = discord.Embed(
            color=discord.Color.blue(),
            title=f"Transfer {from_user.name} -> {to_user.name}",
            description=(
                f"You are about to transfer \"ownership\" of `{data['twitch_name']}` "
                f"to {to_user.mention} (orginal owner {from_user.mention}) "
                "points will not be affected, (admin status will be updated if needed)"
            ),
        )

        confirm_button = manage_components.create_button(
            style=manage_components.ButtonStyle.red, label="confirm", emoji="☑️"
        )
        cancel_button = manage_components.create_button(
            style=manage_components.ButtonStyle.blue, label="cancel", emoji="⛔"
        )

        row = manage_components.create_actionrow(confirm_button, cancel_button)

        await ctx.send(
            embed=conformation_embed, components=[row], hidden=constants.HIDE_MESSAGES
        )

        button_ctx = await manage_components.wait_for_component(
            self.bot, components=row
        )

        confirm_button["disabled"] = True
        cancel_button["disabled"] = True
        row = manage_components.create_actionrow(confirm_button, cancel_button)

        if button_ctx.custom_id == cancel_button["custom_id"]:
            conformation_embed.color = discord.Color.red()
            conformation_embed.title += ": **CANCELD**"

            await button_ctx.edit_origin(embed=conformation_embed, components=[row])

        else:  # we assume we dont have other buttons
            conformation_embed.color = discord.Color.green()
            conformation_embed.title += ": **COMPLETED**"

            new_data = {
                "discord_name": f"{ctx.author.name}#{ctx.author.discriminator}",
                "discord_id": str(ctx.author.id),
            }
            self.members.update_one({"_id": data["_id"]}, {"$set": new_data})

            await button_ctx.edit_origin(embed=conformation_embed, components=[row])

    @commands.Cog.listener()
    async def on_member_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        wasAdmin = any(role.id == constants.ADMIN_ROLE_ID for role in before.roles)
        isAdmin = any(role.id == constants.ADMIN_ROLE_ID for role in after.roles)

        if wasAdmin != isAdmin:
            logger.info(f"updating {after.id}['isAdmin'] = {isAdmin}")
            self.members.update_one(
                {"discord_id": str(after.id)}, {"$set": {"isAdmin": isAdmin}}
            )

        b_nick = f"{before.name}#{before.discriminator}"
        a_nick = f"{after.name}#{after.discriminator}"

        if b_nick != a_nick:
            logger.info(f"updating {after.id}['discord_name'] = {a_nick}")
            self.members.update_one(
                {"discord_id": str(after.id)}, {"$set": {"discord_name": a_nick}}
            )


def setup(bot: Bot) -> None:
    bot.add_cog(Twitch(bot))

"""Main cog for interacting with the db."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, cast

import discord
import discord_slash
from discord.ext import commands
from discord_slash import cog_ext, manage_commands, manage_components
from discord_slash.model import SlashCommandOptionType
from loguru import logger

from bot import constants
from bot.constants import GUILD_ID
from bot.paginator import EmbedPaginator
from bot.types import TwitchUserResponseCorrect, TwitchUserResponseError

if TYPE_CHECKING:
    from typing import Optional

    from discord_slash import SlashContext

    from bot.bot import Bot
    from bot.types import MemberData, TwitchData, TwitchUserResponse

# matches:
# https://twitch.tv/username
# http://twitch.tv/username
# twitch.tv/username
# (if this does not match we assume it is just a normal username)
TWITCH_URL = re.compile(r"^(https?:\/\/)?twitch\.tv\/(.+)$")

TWITCH_TOKEN_ENDPOINT = "https://id.twitch.tv/oauth2/token"  # noqa: S105
TWITCH_USER_ENDPOINT = "https://api.twitch.tv/helix/users"


class Twitch(commands.Cog):
    """Cog taking care of accounts in db."""

    token: str

    def __init__(self, bot: Bot):
        """
        Create an instance.

        Args:
            bot: the bot this cog is a part of
        """
        self.bot = bot
        self.members = bot.members

    async def sync_admins(self) -> None:
        """
        Make sure all admins are correct on bot restart.

        Raises:
            ValueError: if guild is not found
        """
        logger.info("syncing admins")

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            raise ValueError("guild not found")

        admins = [
            str(member.id)
            for member in guild.members
            if any(role.id == constants.ADMIN_ROLE_ID for role in member.roles)
        ]

        self.members.update_many(
            {"discord_id": {"$in": admins}}, {"$set": {"isAdmin": True}}
        )
        self.members.update_many(
            {"discord_id": {"$ne": None, "$exists": True, "$nin": admins}},
            {"$set": {"isAdmin": False}},
        )

        logger.info("synced admins.")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Get twitch token and sync admins."""
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

    async def get_twithc_data(self, twitch_name: str) -> Optional[TwitchData]:
        """
        Get data from twitch based on login name.

        Args:
            twitch_name: name to lookup

        Returns:
            the data from twitch
        """
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Client-Id": constants.TWITCH_CLIENT_ID,
        }
        params = {"login": twitch_name}

        async with self.bot.http_session.get(
            TWITCH_USER_ENDPOINT, params=params, headers=headers
        ) as resp:
            raw_data: TwitchUserResponse = await resp.json()

        if "error" in raw_data:
            raw_data = cast(TwitchUserResponseError, raw_data)
            logger.error(raw_data["message"])
            return None

        raw_data = cast(TwitchUserResponseCorrect, raw_data)
        data = raw_data["data"]
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
        """
        Register a twitch user name.

        Will branch off to other relevant function depending on context.

        Args:
            ctx: the interaction context
            twitch_name: user given twitch login name (can be url)
        """
        logger.info(f"registering {twitch_name} <-> {ctx.author}")
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

        duplicate_twitch_document: Optional[MemberData] = self.members.find_one(
            {"twitch_id": twitch_data["id"]},
        )
        if duplicate_twitch_document is not None:
            if duplicate_twitch_document.get("discord_id", None) is None:
                await self.link_twitch(ctx, duplicate_twitch_document, twitch_data)
                return

            logger.info("already owned twitch account.")
            mention = f"<@{duplicate_twitch_document['discord_id']}>"

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

        duplicate_discord_docuemnt: Optional[MemberData] = self.members.find_one(
            {"discord_id": str(ctx.author.id)}
        )
        if duplicate_discord_docuemnt is None:
            await self.register_new(ctx, twitch_data)
        else:
            await self.update_twitch(ctx, duplicate_discord_docuemnt, twitch_data)

    async def register_new(self, ctx: SlashContext, twitch_data: TwitchData) -> None:
        """
        Create a new account.

        Args:
            ctx: the interaction context
            twitch_data: twitch account data
        """
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
            text="You can change this later using /twitch register"
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
            conformation_embed.title += ": **CANCELD**"  # type: ignore

            await button_ctx.edit_origin(embed=conformation_embed, components=[row])
            logger.info(f"canceld {ctx.author.name}")

        else:  # we assume we dont have other buttons
            conformation_embed.color = discord.Color.green()
            conformation_embed.title += ": **COMPLETED**"  # type: ignore

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
            logger.info(f"registerd {ctx.author.name}")

            await button_ctx.edit_origin(embed=conformation_embed, components=[row])

    async def update_twitch(
        self, ctx: SlashContext, duplicate: MemberData, twitch_data: TwitchData
    ) -> None:
        """
        Overwrite twitch username.

        Args:
            ctx: the interaction context
            duplicate: the already exsisting db entry
            twitch_data: twitch account data
        """
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
            conformation_embed.title += ": **CANCELD**"  # type: ignore

            await button_ctx.edit_origin(embed=conformation_embed, components=[row])
            logger.info(f"canceld {ctx.author.name}")

        else:  # we assume we dont have other buttons
            conformation_embed.color = discord.Color.green()
            conformation_embed.title += ": **COMPLETED**"  # type: ignore

            data = {
                "twitch_name": twitch_data["login"].lower(),
                "twitch_id": twitch_data["id"],
                "points": 0,
            }

            logger.info(f"updated {ctx.author.name}")
            self.members.update_one({"_id": duplicate["_id"]}, {"$set": data})

            await button_ctx.edit_origin(embed=conformation_embed, components=[row])

    async def link_twitch(
        self, ctx: SlashContext, duplicate: MemberData, twitch_data: TwitchData
    ) -> None:
        """
        Link a discord account to a already existing twitch db entry.

        Args:
            ctx: the interaction context
            duplicate: the already exsisting db entry
            twitch_data: twitch account data
        """
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
            conformation_embed.title += ": **CANCELD**"  # type: ignore

            await button_ctx.edit_origin(embed=conformation_embed, components=[row])
            logger.info(f"canceld {ctx.author.name}")

        else:  # we assume we dont have other buttons
            conformation_embed.color = discord.Color.green()
            conformation_embed.title += ": **COMPLETED**"  # type: ignore

            data = {
                "discord_name": f"{ctx.author.name}#{ctx.author.discriminator}",
                "discord_id": str(ctx.author.id),
            }
            self.members.update_one({"_id": duplicate["_id"]}, {"$set": data})

            logger.info(f"linked {ctx.author.name}")

            await button_ctx.edit_origin(embed=conformation_embed, components=[row])

    def format_data_for_discord(self, data: MemberData) -> discord.Embed:
        """
        Format raw db data into a discord embed.

        Args:
            data: db data to format

        Returns:
            formatted discord embed
        """
        embed = discord.Embed(title=f"Data for user `{data['discord_name']}`")

        for name, value in data.items():
            if name in {"_id", "twitch_id", "discord_id", "stream"}:
                continue

            if value is not None and value != "":
                embed.add_field(name=name, value=str(value))  # , inline=False)

        return embed

    async def delete_popup(self, ctx: SlashContext, data: MemberData) -> None:
        """
        Create a popup to make sure they want to delete an account.

        Args:
            ctx: the interaction context to create popup in
            data: data/user to create popup for
        """
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
            logger.info(f"canceld {ctx.author.name}")

        elif int_ctx.custom_id == are_you_sure["custom_id"]:
            embed.color = discord.Color.red()
            embed.title += ": **DELETED**"

            self.members.delete_one({"_id": data["_id"]})
            await int_ctx.edit_origin(embed=embed, components=[row])

            logger.info(f"deleted {ctx.author.name}")

    @cog_ext.cog_subcommand(
        base="twitch",
        name="unregister",
        description="remove your discord -> twitch link from our systems.",
        guild_ids=[GUILD_ID],
    )
    async def unregister(self, ctx: SlashContext) -> None:
        """
        Unregister activating user.

        Args:
            ctx: the interaction context
        """
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
            logger.info(f"unregister popup {ctx.author.name}")
            await self.delete_popup(ctx, data)

    @cog_ext.cog_subcommand(
        base="twitch",
        name="points",
        description="check your points",
        options=[],
        guild_ids=[GUILD_ID],
    )
    async def points_command(self, ctx: SlashContext) -> None:
        """
        Get points of activating user.

        Args:
            ctx: the interaction context
        """
        await ctx.defer(hidden=constants.HIDE_MESSAGES)
        user_data = self.members.find_one({"discord_id": str(ctx.author.id)})
        if user_data is None:
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
            points = user_data["points"]
            points_embed = discord.Embed(
                color=discord.Color.blue(),
                title=f"Points for {user_data['twitch_name']}",
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
        """
        Delete an account.

        Args:
            ctx: the interaction context
            user: user to delete account of.
        """
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
        name="view",
        description="view somebody elses database entry.",
        options=[
            manage_commands.create_option(
                name="user",
                description="the user to view the entry of",
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
    async def view_command(self, ctx: SlashContext, user: discord.User) -> None:
        """
        View database entry of one discord user.

        Args:
            ctx: the interaction context
            user: user to view entry of.
        """
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
            embed = self.format_data_for_discord(data)
            await ctx.send(embed=embed, hidden=constants.HIDE_MESSAGES)

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
        """
        View all database entries.

        Args:
            ctx: the interaction context
        """
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
        self,
        ctx: SlashContext,
        from_user: discord.User,
        to_user: discord.User,
    ) -> None:
        """
        Transfere owner ship of a account.

        Args:
            ctx: the interaction context
            from_user: user to transfere from
            to_user: user to transfere to
        """
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
            conformation_embed.title += ": **CANCELD**"  # type: ignore

            await button_ctx.edit_origin(embed=conformation_embed, components=[row])

        else:  # we assume we dont have other buttons
            conformation_embed.color = discord.Color.green()
            conformation_embed.title += ": **COMPLETED**"  # type: ignore

            new_data = {
                "discord_name": f"{ctx.author.name}#{ctx.author.discriminator}",
                "discord_id": str(ctx.author.id),
            }
            self.members.update_one({"_id": data["_id"]}, {"$set": new_data})

            await button_ctx.edit_origin(embed=conformation_embed, components=[row])

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before: discord.Member,
        after: discord.Member,
    ) -> None:
        """
        Detect admin and name changes.

        Args:
            before: state of user before update
            after: state of user after update
        """
        was_admin = any(role.id == constants.ADMIN_ROLE_ID for role in before.roles)
        is_admin = any(role.id == constants.ADMIN_ROLE_ID for role in after.roles)

        if was_admin != is_admin:
            logger.info(f"updating {after.id}['isAdmin'] = {is_admin}")
            self.members.update_one(
                {"discord_id": str(after.id)},
                {"$set": {"isAdmin": is_admin}},
            )

        b_nick = f"{before.name}#{before.discriminator}"
        a_nick = f"{after.name}#{after.discriminator}"

        if b_nick != a_nick:
            logger.info(f"updating {after.id}['discord_name'] = {a_nick}")
            self.members.update_one(
                {"discord_id": str(after.id)},
                {"$set": {"discord_name": a_nick}},
            )


def setup(bot: Bot) -> None:
    """
    Add cog to bot.

    Args:
        bot: bot to add cog to.
    """
    bot.add_cog(Twitch(bot))

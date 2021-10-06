"""Commands under the /twitch group."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

import aiohttp
import hikari
import tanjun

from bot import constants, injectors, utils
from bot.types import TwitchErrorResponse, TwitchUserData

if TYPE_CHECKING:
    from motor import motor_asyncio as motor

    from bot.types import MemberDocument, TwitchResponse


TWITCH_URL = re.compile(r"^(https?:\/\/)?twitch\.tv\/(.+)$")

# it think this might contain a password because of the "token"
TWITCH_TOKEN_ENDPOINT = "https://id.twitch.tv/oauth2/token"  # noqa: S105
TWITCH_USER_ENDPOINT = "https://api.twitch.tv/helix/users"


component = tanjun.Component()
twitch_group = tanjun.slash_command_group(
    "twitch", "commands for interacting with our account system."
)


@component.with_listener(hikari.StartedEvent)
async def grab_twitch_token(
    event: hikari.StartedEvent,
    http_session: aiohttp.ClientSession = tanjun.injected(
        type=aiohttp.ClientSession
    ),
) -> None:
    """
    Get twich token from twitch api.

    Args:
        event (hikari.StartedEvent): Start event
        http_session (aiohttp.ClientSession, optional): Http session to make request with
    """
    params = {
        "client_id": constants.TWITCH_CLIENT_ID,
        "client_secret": constants.TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }

    async with http_session.post(TWITCH_TOKEN_ENDPOINT, params=params) as resp:
        data = await resp.json()

    component.metadata["twitch_token"] = data["access_token"]


async def get_twitch_data(
    http_session: aiohttp.ClientSession, username: str
) -> None | TwitchUserData:
    """
    Get data on a twitch user.

    Args:
        http_session (aiohttp.ClientSession): Http session to make request with
        username (str): username to lookup

    Raises:
        Exception: An error was returned from the twitch api

    Returns:
        None | TwitchUserData: The data from the user, or None if not found
    """
    headers = {
        "Authorization": f"Bearer {component.metadata['twitch_token']}",
        "Client-Id": constants.TWITCH_CLIENT_ID,
    }
    params = {"login": username}

    async with http_session.get(
        TWITCH_USER_ENDPOINT, params=params, headers=headers
    ) as resp:
        raw_data: TwitchResponse = await resp.json()

    if "error" in raw_data:
        raw_data = cast(TwitchErrorResponse, raw_data)
        raise Exception(raw_data["message"])

    data = raw_data["data"]
    if len(data) == 0:
        return None
    else:
        user_data = data[0]

        return cast(TwitchUserData, {**user_data, "id": int(user_data["id"])})


@twitch_group.with_command
@tanjun.with_str_slash_option("username", "your twitch user name")
@tanjun.as_slash_command(
    "register", "register your twitch account in our system."
)
async def command_register(
    ctx: tanjun.SlashContext,
    username: str,
    http_session: aiohttp.ClientSession = tanjun.injected(
        type=aiohttp.ClientSession
    ),
    members: motor.AsyncIOMotorCollection[MemberDocument] = tanjun.injected(
        callback=injectors.get_members_db
    ),
) -> None:
    """
    Register a twitch user.

    Args:
        ctx (tanjun.SlashContext): The commands context
        username (str): twitch username to register
        http_session (aiohttp.ClientSession, optional): HttpSession to make requests with
        members (motor.AsyncIOMotorCollection[MemberDocument], optional):
            db collection to edit
    """
    await ctx.defer()

    # detect url
    if match := TWITCH_URL.fullmatch(username):
        username = match.groups()[1]

    twitch_data = await get_twitch_data(http_session, username)

    if twitch_data is None:
        # Twitch user not found
        error_embed = hikari.Embed(
            title="Can not find twitch account.",
            description=f"could not find twitch account `{username}`",
            color=constants.Colors.RED,
        )
        await ctx.respond(embed=error_embed)
        return

    twitch_user_in_db = await members.find_one({"twitch_id": twitch_data["id"]})
    if twitch_user_in_db is not None:
        if twitch_user_in_db.get("discord_id") is None:
            # no discord account linked, lets do that
            await link_exsisting_twitch_to_discord(
                ctx, members, twitch_user_in_db, twitch_data
            )
        else:  # account it taken by somebody else
            error_embed = hikari.Embed(
                title="Account already registerd",
                description=(
                    f"<@{twitch_user_in_db['discord_id']}>"
                    "had already claimed this twitch account. "
                    "if they are not the owner of that twitch account, "
                    "please contact an admin."
                ),
                color=constants.Colors.RED,
            ).set_thumbnail(twitch_data["profile_image_url"])
            await ctx.respond(embed=error_embed)

    else:
        discord_user_in_db = await members.find_one(
            {"discord_id": str(ctx.author.id)}
        )
        if discord_user_in_db is None:
            await register_new(ctx, members, twitch_data)
        else:
            await overwrite_twitch(
                ctx, members, discord_user_in_db, twitch_data
            )


async def register_new(
    ctx: tanjun.SlashContext,
    members: motor.AsyncIOMotorCollection[MemberDocument],
    twitch_data: TwitchUserData,
) -> None:
    """
    Register a new twitch user.

    Args:
        ctx (tanjun.SlashContext): Context to create messages in
        members (motor.AsyncIOMotorCollection[MemberDocument]): Database to add user to
        twitch_data (TwitchUserData): Twitch data from user to register
    """

    async def perform_update() -> None:
        author = await ctx.rest.fetch_member(constants.GUILD_ID, ctx.author)

        await members.insert_one(
            {
                "discord_id": str(author.id),
                "discord_name": f"{author.username}#{author.discriminator}",
                "twitch_id": twitch_data["id"],
                "twitch_name": twitch_data["login"],
                "points": 0,
                "isAdmin": utils.is_admin(author),
            }
        )

    username = twitch_data["login"]
    await utils.confirmation_embed(
        ctx,
        callback=perform_update(),
        embed=(
            hikari.Embed(
                title="Register new user",
                description=(
                    "You are about to register"
                    f"[{username}](https://www.twitch.tv/{username})"
                    " Make sure this is your account."
                ),
                color=constants.Colors.BLUE,
            ).set_thumbnail(twitch_data["profile_image_url"])
        ),
        confirm_button=utils.ButtonInfo("Register", hikari.ButtonStyle.SUCCESS),
    )


async def overwrite_twitch(
    ctx: tanjun.SlashContext,
    members: motor.AsyncIOMotorCollection[MemberDocument],
    old_document: MemberDocument,
    twitch_data: TwitchUserData,
) -> None:
    """
    Overwrite exsisting twitch data for account.

    Args:
        ctx (tanjun.SlashContext): Context to create messages in
        members (motor.AsyncIOMotorCollection[MemberDocument]):
            Database to edit account in
        old_document (MemberDocument): Exsisting account data
        twitch_data (TwitchUserData): New twitch data
    """

    async def perform_update() -> None:
        await members.update_one(
            {"_id": old_document["_id"]},
            {
                "$set": {
                    "twitch_id": twitch_data["id"],
                    "twitch_name": twitch_data["login"],
                    "points": 0,
                }
            },
        )

    old_username: str = old_document["twitch_name"]
    username: str = twitch_data["login"]

    await utils.confirmation_embed(
        ctx,
        callback=perform_update(),
        embed=(
            hikari.Embed(
                title="Overwrite user",
                color=constants.Colors.BLUE,
                description=(
                    "You are about to overwrite "
                    f"[{old_username}](https://www.twitch.tv/{old_username}) "
                    f"with [{username}](https://www.twitch.tv/{username})! "
                    "\n\n**WARNING:** This will reset your points."
                ),
            ).set_thumbnail(twitch_data["profile_image_url"])
        ),
        confirm_button=utils.ButtonInfo("Overwrite", hikari.ButtonStyle.DANGER),
        deny_button=utils.ButtonInfo("Cancel", hikari.ButtonStyle.PRIMARY),
    )


async def link_exsisting_twitch_to_discord(
    ctx: tanjun.SlashContext,
    members: motor.AsyncIOMotorCollection[MemberDocument],
    document: MemberDocument,
    twitch_data: TwitchUserData,
) -> None:
    """
    Add discord link to twitch account.

    Args:
        ctx (tanjun.SlashContext): Context to create messages in
        members (motor.AsyncIOMotorCollection[MemberDocument]): Db to edit account in
        document (MemberDocument): Exsisting account data
        twitch_data (TwitchUserData): Twitch data for user
    """

    async def perform_update() -> None:
        member = await ctx.rest.fetch_member(constants.GUILD_ID, ctx.author.id)
        await members.update_one(
            {"_id": document["_id"]},
            {
                "$set": {
                    "discord_id": str(member.id),
                    "discord_name": f"{member.username}#{member.discriminator}",
                }
            },
        )

    username = twitch_data["login"]
    await utils.confirmation_embed(
        ctx,
        callback=perform_update(),
        embed=(
            hikari.Embed(
                title="Register new user",
                description=(
                    "You are about to register"
                    f"[{username}](https://www.twitch.tv/{username})",
                    " Make sure this is your account.",
                ),
                color=constants.Colors.BLUE,
            ).set_thumbnail(twitch_data["profile_image_url"])
        ),
        confirm_button=utils.ButtonInfo("Register", hikari.ButtonStyle.SUCCESS),
    )


@twitch_group.with_command
@tanjun.as_slash_command("unregister", "remove your account.")
async def command_unregister(
    ctx: tanjun.SlashContext,
    members: motor.AsyncIOMotorCollection[MemberDocument] = tanjun.injected(
        callback=injectors.get_members_db
    ),
) -> None:
    """
    Remove account from db.

    Args:
        ctx (tanjun.SlashContext): The commands context
        members (motor.AsyncIOMotorCollection[MemberDocument], optional):
            Db to remove account from.
    """
    document = await members.find_one({"discord_id": str(ctx.author.id)})
    if document is None:
        error_embed = hikari.Embed(
            title="Account not found.",
            color=constants.Colors.RED,
            description="It does not look like you have an account registerd.",
        )
        await ctx.respond(embed=error_embed)
        return

    async def perform_delete() -> None:
        await members.delete_one({"_id": document["_id"]})

    await utils.confirmation_embed(
        ctx,
        callback=perform_delete(),
        embed=hikari.Embed(
            title="Delete account",
            color=constants.Colors.BLUE,
            description="**WARNING:** this will remove your points!",
        ),
        confirm_button=utils.ButtonInfo("Delete", hikari.ButtonStyle.DANGER),
        deny_button=utils.ButtonInfo("Cancel", hikari.ButtonStyle.PRIMARY),
    )


@twitch_group.with_command
@tanjun.as_slash_command("points", "get your points.")
async def command_points(
    ctx: tanjun.SlashContext,
    members: motor.AsyncIOMotorCollection[MemberDocument] = tanjun.injected(
        callback=injectors.get_members_db
    ),
) -> None:
    """
    See users points.

    Args:
        ctx (tanjun.SlashContext): The slash commands context.
        members (motor.AsyncIOMotorCollection[MemberDocument], optional):
            Db to get points from.
    """
    document = await members.find_one({"discord_id": str(ctx.author.id)})
    if document is None:
        error_embed = hikari.Embed(
            title="Account not found.",
            color=constants.Colors.RED,
            description="It does not look like you have an account registerd.",
        )
        await ctx.respond(embed=error_embed)
        return

    points = document["points"]
    embed = hikari.Embed(
        title="Your points!",
        color=constants.Colors.YELLOW,
        description=f"You have **{points}** points!",
    )
    await ctx.respond(embed=embed)


component.add_slash_command(twitch_group)


@component.with_listener(hikari.MemberDeleteEvent)
async def remove_members_when_they_leave(
    event: hikari.MemberDeleteEvent,
    members: motor.AsyncIOMotorCollection[MemberDocument] = tanjun.injected(
        callback=injectors.get_members_db
    ),
) -> None:
    """
    Remove a member from db when they leave.

    Args:
        event (hikari.MemberDeleteEvent): The user leave event
        members (motor.AsyncIOMotorCollection[MemberDocument], optional):
            Db to remove user from.
    """
    await members.delete_one({"discord_id": str(event.user_id)})


@component.with_listener(hikari.MemberUpdateEvent)
async def update_member_nickname(
    event: hikari.MemberUpdateEvent,
    members: motor.AsyncIOMotorCollection[MemberDocument] = tanjun.injected(
        callback=injectors.get_members_db
    ),
) -> None:
    """
    Update users nickname when they change it.

    Args:
        event (hikari.MemberUpdateEvent): the member update event
        members (motor.AsyncIOMotorCollection[MemberDocument], optional):
            Db to edit name in.
    """
    current_name = f"{event.member.username}#{event.member.discriminator}"
    await members.update_one(
        {"discord_id": str(event.user_id)},
        {"$set": {"discord_name": current_name}},
    )


@tanjun.as_loader
def load_component(client: tanjun.Client) -> None:
    """
    Add commands to client.

    Args:
        client (tanjun.Client): Client to add commands to
    """
    client.add_component(component)

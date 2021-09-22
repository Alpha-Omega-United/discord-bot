from __future__ import annotations

from typing import TYPE_CHECKING, cast

import hikari
import tanjun

from bot import constants, injectors, utils

if TYPE_CHECKING:
    from typing import Any, Dict, Optional

    from motor import motor_asyncio as motor


component = tanjun.Component()


@component.with_listener(hikari.StartedEvent)
async def sync_admins(
    event: hikari.StartedEvent,
    bot: hikari.GatewayBot = tanjun.injected(type=hikari.GatewayBot),
    members: motor.AsyncIOMotorCollection = tanjun.injected(
        callback=injectors.get_members_db
    ),
) -> None:
    guild = await bot.rest.fetch_guild(constants.GUILD_ID)
    admin_ids = []
    for member_id, member in guild.get_members().items():
        if utils.is_admin(member):
            admin_ids.append(str(member_id))

    await members.update_many(
        {"discord_in": {"$in": admin_ids}}, {"$set": {"isAdmin": True}}
    )
    await members.update_many(
        {"discord_id": {"$ne": None, "$exists": True, "$nin": admin_ids}},
        {"$set": {"isAdmin": False}},
    )


@component.with_listener(hikari.MemberUpdateEvent)
async def detect_admin_change(
    event: hikari.MemberUpdateEvent,
    members: motor.AsyncIOMotorCollection = tanjun.injected(
        callback=injectors.get_members_db
    ),
) -> None:
    is_admin = utils.is_admin(event.member)
    await members.update_one(
        {"discord_id": str(event.user_id)}, {"$set": {"isAdmin": is_admin}}
    )


admin_group = tanjun.slash_command_group(
    "admin",
    "commands for interacting with our account system using your admin powers!",
    default_permission=False,
)


def format_data_for_discord(document: Dict[str, Any]) -> hikari.Embed:
    return (
        hikari.Embed(title="Data for user.", color=constants.Colors.BLUE)
        .add_field("twitch_name", str(document.get("twitch_name")), inline=True)
        .add_field(
            "discord_name", str(document.get("discord_name")), inline=True
        )
        .add_field("points", document["points"], inline=True)
        .add_field("isAdmin", document["isAdmin"], inline=True)
    )


@admin_group.with_command
@tanjun.with_member_slash_option("discord", "discord member", default=None)
@tanjun.with_str_slash_option("twitch", "twitch name", default=None)
@tanjun.as_slash_command("view", "view somebodies db entry.")
async def command_view_db_entry(
    ctx: tanjun.SlashContext,
    twitch: Optional[str],
    discord: Optional[hikari.Member],
    members: motor.AsyncIOMotorCollection = tanjun.injected(
        callback=injectors.get_members_db
    ),
) -> None:
    if (twitch is None) == (discord is None):
        await ctx.respond("Please only provide one of `twitch` or `discord`")
        return

    if twitch is not None:
        document = await members.find_one({"twitch_name": twitch})
    else:
        discord = cast(hikari.Member, discord)
        document = await members.find_one({"discord_id": str(discord.id)})

    if document is None:
        await ctx.respond("Account not found.")
        return

    embed = format_data_for_discord(document)
    await ctx.respond(embed=embed)


@admin_group.with_command
@tanjun.with_member_slash_option("to_user", "new account owner.")
@tanjun.with_member_slash_option("from_user", "current account owner.")
@tanjun.as_slash_command(
    "tranfere", "transfere 'ownership' of a twitch account."
)
async def command_tranfere(
    ctx: tanjun.SlashContext,
    from_user: hikari.Member,
    to_user: hikari.Member,
    members: motor.AsyncIOMotorCollection = tanjun.injected(
        callback=injectors.get_members_db
    ),
) -> None:
    document = await members.find_one({"discord_id": str(from_user.id)})
    if document is None:
        await ctx.respond("Account not found.")
        return

    async def perform_transfere() -> None:
        await members.update_one(
            {"_id": document["_id"]},
            {
                "$set": {
                    "discord_name": f"{to_user.username}#{to_user.discriminator}",
                    "discord_id": str(to_user.id),
                }
            },
        )

    embed = format_data_for_discord(document)
    embed.title = f"Transfere to {to_user}"
    await utils.confirmation_embed(
        ctx,
        callback=perform_transfere(),
        embed=embed,
        confirm_button=utils.ButtonInfo("tranfere", hikari.ButtonStyle.DANGER),
        deny_button=utils.ButtonInfo("cancel", hikari.ButtonStyle.PRIMARY),
    )


component.add_slash_command(admin_group)


@component.with_listener(hikari.StartedEvent)
async def make_admin_admin_only(
    event: hikari.StartedEvent,
    rest: hikari.impl.RESTClientImpl = tanjun.injected(
        type=hikari.impl.RESTClientImpl
    ),
) -> None:
    application = await rest.fetch_application()
    commands = await rest.fetch_application_commands(
        application, constants.GUILD_ID
    )
    command = next(
        command for command in commands if command.name == admin_group.name
    )

    permissions = [
        hikari.CommandPermission(
            type=hikari.CommandPermissionType.ROLE,
            id=constants.ADMIN_ROLE_ID,
            has_access=True,
        )
    ]
    await rest.set_application_command_permissions(
        application, constants.GUILD_ID, command, permissions
    )


@tanjun.as_loader
def load_component(client: tanjun.Client) -> None:
    client.add_component(component)

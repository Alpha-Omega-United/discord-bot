"""Role info commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

import hikari
import tanjun

from bot import constants, injectors

if TYPE_CHECKING:
    from motor import motor_asyncio as motor

    from bot.types import RoleInfoDocument


component = tanjun.Component()


@component.with_listener(hikari.StartedEvent)
async def sync_roles(
    event: hikari.StartedEvent,
    bot: hikari.GatewayBot = tanjun.injected(type=hikari.GatewayBot),
    role_info: motor.AsyncIOMotorCollection[RoleInfoDocument] = tanjun.injected(
        callback=injectors.get_role_info_db
    ),
) -> None:
    """
    Sync roles in the guild with the db.

    Args:
        event (hikari.StartedEvent): The start event.
        bot (hikari.GatewayBot, optional): Bot to get guild date from.
        role_info (motor.AsyncIOMotorCollection[RoleInfoDocument], optional):
            Db to store role info in.
    """
    guild = await bot.rest.fetch_guild(constants.GUILD_ID)

    for role_id, role in guild.get_roles().items():
        await role_info.update_one(
            {"role_id": role_id},
            {
                "$set": {"name": role.name, "color": role.color.raw_hex_code},
                "$setOnInsert": {
                    "role_id": role_id,
                    "description": "No description provided yet.",
                },
            },
            upsert=True,
        )


@component.with_listener(hikari.RoleCreateEvent)
async def create_new_role(
    event: hikari.RoleCreateEvent,
    role_info: motor.AsyncIOMotorCollection[RoleInfoDocument] = tanjun.injected(
        callback=injectors.get_role_info_db
    ),
) -> None:
    """
    Store new role when one is created.

    Args:
        event (hikari.RoleCreateEvent): Role created event
        role_info (motor.AsyncIOMotorCollection[RoleInfoDocument], optional):
            Db to store role info in.
    """
    role = event.role
    await role_info.insert_one(
        {
            "name": role.name,
            "color": role.color.raw_hex_code,
            "role_id": role.id,
            "description": "No description provided yet.",
        }
    )


@component.with_listener(hikari.RoleDeleteEvent)
async def remove_deleted_roles(
    event: hikari.RoleDeleteEvent,
    role_info: motor.AsyncIOMotorCollection = tanjun.injected(
        callback=injectors.get_role_info_db
    ),
) -> None:
    """
    Remove role when it is deleted.

    Args:
        event (hikari.RoleDeleteEvent): Role delete event
        role_info (motor.AsyncIOMotorCollection, optional): Db to remove role from.
    """
    await role_info.delete_one({"role_id": event.role_id})


@component.with_listener(hikari.RoleUpdateEvent)
async def store_new_role_info(
    event: hikari.RoleUpdateEvent,
    role_info: motor.AsyncIOMotorCollection[RoleInfoDocument] = tanjun.injected(
        callback=injectors.get_role_info_db
    ),
) -> None:
    """
    Update role info when role is updated.

    Args:
        event (hikari.RoleUpdateEvent): Role update event
        role_info (motor.AsyncIOMotorCollection[RoleInfoDocument], optional):
            Db to update info in.
    """
    await role_info.update_one(
        {"role_id": event.role_id},
        {
            "$set": {
                "name": event.role.name,
                "color": event.role.color.raw_hex_code,
            }
        },
    )


@component.with_slash_command
@tanjun.with_role_slash_option("role", "role to get description of")
@tanjun.as_slash_command("role", "get information on a role")
async def command_role(
    ctx: tanjun.SlashContext,
    role: hikari.Role,
    role_info: motor.AsyncIOMotorCollection[RoleInfoDocument] = tanjun.injected(
        callback=injectors.get_role_info_db
    ),
) -> None:
    """
    Get description of role.

    Args:
        ctx (tanjun.SlashContext): The commands context.
        role (hikari.Role): The role to get info of.
        role_info (motor.AsyncIOMotorCollection[RoleInfoDocument], optional):
            Db to get info from.
    """
    role_data = await role_info.find_one({"role_id": role.id})

    if role_data is None:
        await ctx.respond(
            "Sorry an unecpected error occured: **Role not found**"
        )
        return

    embed = hikari.Embed(
        title=role.name, color=role.color, description=role_data["description"]
    )

    await ctx.respond(embed=embed)


@tanjun.as_loader
def load_component(client: tanjun.Client) -> None:
    """
    Add component to client.

    Args:
        client (tanjun.Client): Client to add component to.
    """
    client.add_component(component)

from __future__ import annotations

from typing import TYPE_CHECKING

import tanjun

from bot import injectors

if TYPE_CHECKING:
    from motor import motor_asyncio as motor

    from bot.types import BirthdayDocument


component = tanjun.Component()


@component.with_slash_command
@tanjun.as_slash_command(
    "birthday", "Register your birthday so we can wish you a happy birthday!"
)
async def command_birthday(
    ctx: tanjun.SlashContext,
    birthday: motor.AsyncIOMotorCollection[BirthdayDocument] = tanjun.injected(
        callback=injectors.get_birthday_db
    ),
) -> None:
    pass


@tanjun.as_loader
def load_component(client: tanjun.Client) -> None:
    client.add_component(component)

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import tanjun

from bot import constants, injectors

if TYPE_CHECKING:
    from motor import motor_asyncio as motor

    from bot.types import BirthdayDocument


DATE_FORMAT = "%d/%m"
HUMAN_DATE_FORMAT = "dd/mm"


component = tanjun.Component()


@component.with_slash_command
@tanjun.with_str_slash_option(
    "date",
    "your birthday, provided in the format of"
    f"{HUMAN_DATE_FORMAT} (day, then a slash, then the month, all as numbers)",
)
@tanjun.as_slash_command(
    "birthday", "Register your birthday so we can wish you a happy birthday!"
)
async def command_birthday(
    ctx: tanjun.SlashContext,
    date: str,
    birthday: motor.AsyncIOMotorCollection[BirthdayDocument] = tanjun.injected(
        callback=injectors.get_birthday_db
    ),
) -> None:
    try:
        date_d = datetime.strptime(date, DATE_FORMAT)
    except ValueError:
        await ctx.respond(
            "**ERROR:** Sorry I had some trouble converting your input to a date,"
            f"please use format `{HUMAN_DATE_FORMAT}`"
        )
        return

    today = datetime.today()
    date_d = datetime(today.year, date_d.month, date_d.day)
    date_d = datetime(
        today.year if date_d > today else today.year + 1,
        date_d.month,
        date_d.day,
    )

    await birthday.update_one(
        {
            "discord_id": ctx.author.id,
        },
        {
            "$set": {"date": date_d, "announced": False},
            "$setOnInsert": {"discord_id": ctx.author.id},
        },
        upsert=True,
    )

    await ctx.respond(
        "great! I will remind everyone at "
        f"<t:{int(date_d.timestamp())}:D> in <#{constants.BIRTHDAY_CHANNEL_ID}> :D"
    )


@tanjun.as_loader
def load_component(client: tanjun.Client) -> None:
    client.add_component(component)

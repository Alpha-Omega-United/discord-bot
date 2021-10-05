from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import hikari
import tanjun
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import constants, injectors

if TYPE_CHECKING:
    from motor import motor_asyncio as motor

    from bot.types import BirthdayDocument


DATE_FORMAT = "%d/%m"
HUMAN_DATE_FORMAT = "dd/mm"


component = tanjun.Component()


async def send_birthday_msg(
    rest: hikari.impl.RESTClientImpl,
    discord_id: int,
) -> None:
    embed = hikari.Embed(
        title="Happy Birthday!",
        description="".join(
            [
                f"it is <@{discord_id}> birthday 🥳\n\n",
                "dont forget to wish them a happy birthday!",
            ]
        ),
        color=constants.Colors.GREEN,
    )

    await rest.create_message(constants.BIRTHDAY_CHANNEL_ID, embed=embed)


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
            "$set": {"date": date_d},
            "$setOnInsert": {"discord_id": ctx.author.id},
        },
        upsert=True,
    )

    await ctx.respond(
        "great! I will remind everyone at "
        f"<t:{int(date_d.timestamp())}:D> in <#{constants.BIRTHDAY_CHANNEL_ID}> :D"
    )


async def check_birthdays(
    rest: hikari.impl.RESTClientImpl,
    birthday_db: motor.AsyncIOMotorCollection[BirthdayDocument],
) -> None:
    today = datetime.today()
    birthdays = await birthday_db.find({"date": {"$lte": today}}).to_list(None)

    for birthday in birthdays:
        await send_birthday_msg(rest, birthday["discord_id"])
        new_date = birthday["date"]
        new_date = datetime(new_date.year + 1, new_date.month, new_date.day)
        await birthday_db.update_one(
            {"_id": birthday["_id"]}, {"$set": {"date": new_date}}
        )


@component.with_listener(hikari.StartedEvent)
async def start_scheduler(
    event: hikari.StartedEvent,
    scheduler: AsyncIOScheduler = tanjun.injected(type=AsyncIOScheduler),
    rest: hikari.impl.RESTClientImpl = tanjun.injected(
        type=hikari.impl.RESTClientImpl
    ),
    birthday: motor.AsyncIOMotorCollection[BirthdayDocument] = tanjun.injected(
        callback=injectors.get_birthday_db
    ),
) -> None:
    scheduler.add_job(check_birthdays, "cron", hour=0, args=[rest, birthday])


@tanjun.as_loader
def load_component(client: tanjun.Client) -> None:
    client.add_component(component)

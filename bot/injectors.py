from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

import aiohttp
import tanjun
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from motor import motor_asyncio as motor

from bot import constants, types

if TYPE_CHECKING:
    from typing import Callable, Type


D = TypeVar("D")  # noqa: VNE001


def _create_collection_injector(
    collection_name: str, type_: Type[D]
) -> Callable[[motor.AsyncIOMotorDatabase], motor.AsyncIOMotorCollection[D]]:
    def injector(
        database: motor.AsyncIOMotorDatabase = tanjun.injected(
            type=motor.AsyncIOMotorDatabase
        ),
    ) -> motor.AsyncIOMotorCollection[D]:
        return database[collection_name]  # type: ignore

    return injector


get_members_db = _create_collection_injector("members", types.MemberDocument)
get_role_info_db = _create_collection_injector(
    "role_info", types.RoleInfoDocument
)
get_birthday_db = _create_collection_injector(
    "birthday", types.BirthdayDocument
)


async def register_in_async_context(
    client: tanjun.Client = tanjun.injected(type=tanjun.Client),
) -> None:
    client.set_type_dependency(aiohttp.ClientSession, aiohttp.ClientSession())


def register_injectors(client: tanjun.Client) -> None:
    scheduler = AsyncIOScheduler()
    scheduler.start()

    (
        client.set_type_dependency(
            motor.AsyncIOMotorDatabase,
            motor.AsyncIOMotorClient(constants.DATABASE_URI)[
                constants.DATABASE_NAME
            ],
        )
        .set_type_dependency(AsyncIOScheduler, scheduler)
        .add_client_callback(
            tanjun.ClientCallbackNames.STARTING, register_in_async_context
        )
    )

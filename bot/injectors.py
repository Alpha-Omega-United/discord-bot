from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
import hikari
import tanjun
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from motor import motor_asyncio as motor

from bot import constants

if TYPE_CHECKING:
    from typing import Callable


def _connect_to_db() -> motor.AsyncIOMotorDatabase:
    return motor.AsyncIOMotorClient(constants.DATABASE_URI)[
        constants.DATABASE_NAME
    ]


def _create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.start()

    return scheduler


def _create_cient_session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession()


def _create_collection_injector(
    collection_name: str,
) -> Callable[[motor.AsyncIOMotorDatabase], motor.AsyncIOMotorCollection]:
    def injector(
        database: motor.AsyncIOMotorDatabase = tanjun.injected(
            type=motor.AsyncIOMotorDatabase
        ),
    ) -> motor.AsyncIOMotorCollection:
        return database[collection_name]

    return injector


get_members_db = _create_collection_injector("members")
get_role_info_db = _create_collection_injector("role_info")


def register_injectors(client: tanjun.Client) -> None:
    (
        client.set_type_dependency(
            motor.AsyncIOMotorDatabase, tanjun.cache_callback(_connect_to_db)
        )
        .set_type_dependency(
            AsyncIOScheduler, tanjun.cache_callback(_create_scheduler)
        )
        .set_type_dependency(
            aiohttp.ClientSession, tanjun.cache_callback(_create_cient_session)
        )
    )

    @client.with_listener(hikari.StoppedEvent)
    async def close_http_session(
        event: hikari.StoppedEvent,
        http_session: aiohttp.ClientSession = tanjun.injected(
            type=aiohttp.ClientSession
        ),
    ) -> None:
        print("closing http session.")
        await http_session.close()

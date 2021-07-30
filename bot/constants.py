import os
import pathlib
from typing import NamedTuple

import dotenv


dotenv.load_dotenv()


def load_required(key: str) -> str:
    value = os.getenv(key, None)
    if value is None:
        raise EnvironmentError(f"Missing envioroment varible {key!r}")
    return value


TOKEN = load_required("DISCORD_TOKEN")

# Default to real server
GUILD_ID = os.getenv("GUILD_ID", 797571990176661504)


class Paths(NamedTuple):
    src = pathlib.Path("bot")
    cogs = src / "cogs"
    resources = src / "resources"

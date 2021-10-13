"""Constants and configs."""
import os
import pathlib

import dotenv
import hikari

dotenv.load_dotenv()

# The reason we need this, is that dns lookup fails with default settings,
# so we need to set the dns severs manually,
# so to stop one dns from ruining our day lets use more than one.

# SOLUTION FROM:
# https://forum.omz-software.com/topic/6751/pymongo-errors-configurationerror-resolver-configuration-could-not-be-read-or-specified-no-nameservers/5

DNS_SERVERS = [
    # Google
    "8.8.8.8",
    "8.8.4.4",
    # Cloudflare
    "1.1.1.1",
]


def load_required(key: str) -> str:
    """
    Load value from env, fails if not found.

    Args:
        key: key to lookup

    Returns:
        the found value

    Raises:
        EnvironmentError: key not found
    """
    value = os.getenv(key, None)
    if value is None:
        raise EnvironmentError(f"Missing envioroment varible {key!r}")
    return value


TOKEN = load_required("DISCORD_TOKEN")

DATABASE_URI = load_required("DATABASE_URI")
DATABASE_NAME = load_required("DATABASE_NAME")

# Testing unhides all messages.
# WARNING: DO NOT ENABLE IN PROD
TESTING = bool(int(os.getenv("TESTING", False)))
HIDE_MESSAGES = not TESTING

# Default to real server
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", 366331361583169537))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", 797573934848802817))

GUILD_ID = int(os.getenv("GUILD_ID", 797571990176661504))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 876494154354528316))
BIRTHDAY_CHANNEL_ID = int(os.getenv("BIRTHDAY_CHANNEL_ID", 801157827145760768))


class Paths:
    """Folder paths."""

    src = pathlib.Path("bot")
    modules = src / "modules"
    resources = src / "resources"


class Colors:
    """Default colors."""

    RED = hikari.Color(0xFF0000)
    GREEN = hikari.Color(0x07E500)
    BLUE = hikari.Color(0x0044F2)
    YELLOW = hikari.Color(0xF7EB02)

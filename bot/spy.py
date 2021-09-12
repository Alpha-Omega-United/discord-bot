"""Functions and classes for logging python events on objects."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Callable, TypeVar, cast

from loguru import logger

if TYPE_CHECKING:
    from typing import Any


T = TypeVar("T")

logger.level("SPY", no=10, color="<yellow>")


def call_proxy(func: Callable[..., T]) -> Callable[..., T]:
    """
    Log calls to this func.

    Args:
        func: func to be logged calls for

    Returns:
        a modified function behaving like the orginal, but logs calls
    """

    @functools.wraps(func)
    def wrapped(*args: Any, **kwargs: Any) -> T:
        args_string = ",".join(str(arg) for arg in args)
        kwargs_string = ",".join(f"{name}={value}" for name, value in kwargs.items())
        call_string = f"{func.__name__}({args_string}, {kwargs_string})"

        logger.log("SPY", call_string)

        return func(*args, **kwargs)

    return wrapped


class _InstanceProxy:
    def __init__(self, source_instance: T) -> None:
        self._source_instance = source_instance

    def __getattribute__(self, name: str) -> Any:
        value = super().__getattribute__("_source_instance").__getattribute__(name)

        if callable(value):
            return call_proxy(value)
        else:
            return value


InstanceProxy = cast(Callable[[T], T], _InstanceProxy)

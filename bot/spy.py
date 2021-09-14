"""Functions and classes for logging python events on objects."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Callable, TypeVar, cast

from loguru import logger

if TYPE_CHECKING:
    from typing import Any


T = TypeVar("T")

logger.level("SPY", no=10, color="<yellow>")


def call_proxy(prefix: str = "") -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Create decorator logging calls.

    Args:
        prefix: prefix before each log message

    Returns:
        Decorator taking a func to log calls to.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
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
            kwargs_string = ",".join(
                f"{name}={value}" for name, value in kwargs.items()
            )
            call_string = f"{prefix}.{func.__name__}({args_string}, {kwargs_string})"

            logger.log("SPY", call_string)

            return func(*args, **kwargs)

        return wrapped

    return decorator


class _InstanceProxy:
    def __init__(self, source_instance: T, prefix: str) -> None:
        self._source_instance = source_instance
        self._prefix = prefix

    def __getattribute__(self, name: str) -> Any:
        value = super().__getattribute__("_source_instance").__getattribute__(name)

        if callable(value):
            return call_proxy(super().__getattribute__("_prefix"))(value)
        else:
            return value


# tell typing hitting that _InstanceProxy just returns the instance given
# ofc this is not true, but to the caller it should look like it.
# this allows us to get better type hinting and auto-completion
# even if it means lying a bit ;)
InstanceProxy = cast(Callable[[T, str], T], _InstanceProxy)

"""Paginator is used to go back and fourth in 'pages' ."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

import discord
from discord_slash import manage_components

if TYPE_CHECKING:
    from typing import Any, Awaitable, Callable, Dict, List, Optional

    import discord_slash

    MESSAGE_KWARGS = Dict[str, Any]


class Paginator(abc.ABC):
    """Base paginator class."""

    def __init__(
        self,
        num_pages: int,
        previous_button: Optional[Dict[str, Any]] = None,
        next_button: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Create paginator.

        Args:
            num_pages: number of total pages
            previous_button: a optional custom button
            next_button: a optional custom button
        """
        self.num_pages = num_pages

        if previous_button is not None:
            self.previous_button = previous_button
        else:
            self.previous_button = manage_components.create_button(
                style=manage_components.ButtonStyle.primary, emoji="⬅️"
            )

        if next_button is not None:
            self.next_button = next_button
        else:
            self.next_button = manage_components.create_button(
                style=manage_components.ButtonStyle.primary, emoji="➡️"
            )

        self.current_page = -1

    @abc.abstractmethod
    async def create_page_n(self, num: int) -> MESSAGE_KWARGS:
        """
        Grab page from provided pages.

        Args:
            num: page number to grab
        """
        ...

    async def switch_to_page_x(
        self,
        send_edit_cmd: Callable[..., Awaitable[Any]],
        number: int,
        **extra_msg_args: Any,
    ) -> None:
        """
        Switched to the given page.

        Args:
            send_edit_cmd: function used tochange/send the new message.
            number: the page number to switch to
            **extra_msg_args: extra arguments to pass to send_edit_cmd
        """
        self.current_page = number

        msg_data = await self.create_page_n(number)

        self.next_button["disabled"] = number == self.num_pages
        self.previous_button["disabled"] = number == 1
        row = manage_components.create_actionrow(self.previous_button, self.next_button)

        await send_edit_cmd(components=[row], **msg_data, **extra_msg_args)

    async def start(
        self,
        client: discord.Client,
        ctx: discord_slash.SlashContext,
        hidden: bool = True,
    ) -> None:
        """
        Start lisining to click events and turn the pages.

        Args:
            client: discord client to use
            ctx: interaction context to use
            hidden: should this be shown only to the one user
        """
        await self.switch_to_page_x(ctx.send, 1, hidden=hidden)

        while True:
            button_ctx = await manage_components.wait_for_component(
                client, components=[self.previous_button, self.next_button]
            )

            if button_ctx.author != ctx.author:
                await button_ctx.send(
                    "Sorry only the original command user can use this button",
                    hidden=True,
                )
            elif button_ctx.custom_id == self.next_button["custom_id"]:
                await self.switch_to_page_x(
                    button_ctx.edit_origin, self.current_page + 1
                )
            else:
                await self.switch_to_page_x(
                    button_ctx.edit_origin, self.current_page - 1
                )


class EmbedPaginator(Paginator):
    """Paginator working on embeds."""

    def __init__(
        self,
        embeds: List[discord.Embed],
        title_prefix: str = "Page: ",
        previous_button: Optional[Dict[str, Any]] = None,
        next_button: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Create EmbedPaginator.

        Args:
            embeds: a list of embeds to be used as pages
            title_prefix: string that gets appended to start of each title
            previous_button: a optional custom button
            next_button: a optional custom button
        """
        super().__init__(
            num_pages=len(embeds),
            previous_button=previous_button,
            next_button=next_button,
        )

        self.embeds = embeds
        self.title_prefix = title_prefix

    async def create_page_n(self, num: int) -> MESSAGE_KWARGS:
        """
        Grab page from provided pages.

        Args:
            num: page number to grab

        Returns:
            the message kwargs to pass
        """
        embed = self.embeds[num - 1]
        embed.title = self.title_prefix + f"**{num}/{self.num_pages}**"

        return {"embed": embed}


class TextPaginator(Paginator):
    """Paginator working on strings."""

    def __init__(
        self,
        pages: List[str],
        first_line_prefix: str = "**Page: ** ",
        previous_button: Optional[Dict[str, Any]] = None,
        next_button: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Create TextPaginator.

        Args:
            pages: a list of strings to be used as pages
            first_line_prefix: string that gets appended to start of each title
            previous_button: a optional custom button
            next_button: a optional custom button
        """
        super().__init__(
            num_pages=len(pages),
            previous_button=previous_button,
            next_button=next_button,
        )

        self.pages = pages
        self.first_line_prefix = first_line_prefix

    async def create_page_n(self, num: int) -> MESSAGE_KWARGS:
        """
        Grab page from provided pages.

        Args:
            num: page number to grab

        Returns:
            the message kwargs to pass
        """
        page = self.pages[num - 1]
        page = f"{self.first_line_prefix} **{num}/{self.num_pages}**\n\n{page}"

        return {"content": page}

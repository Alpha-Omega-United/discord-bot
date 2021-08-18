import abc
import asyncio
from typing import Any, Awaitable, Callable, Dict, List

import discord
import discord_slash
from discord_slash import manage_components

MESSAGE_KWARGS = Dict[str, Any]


class Paginator(abc.ABC):
    def __init__(self, num_pages: int, previous_button=None, next_button=None):
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

        self.current_page = None
        self.close_timer_task = None

    @abc.abstractmethod
    async def create_page_n(self, num: int) -> MESSAGE_KWARGS:
        ...

    async def switch_to_page_x(
        self,
        send_edit_cmd: Callable[..., Awaitable[Any]],
        number: int,
        **extra_msg_args: Any,
    ) -> None:
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
        hidden=True,
        timeout=60 * 10,
    ) -> None:
        await self.switch_to_page_x(ctx.send, 1, hidden=hidden)

        while True:
            button_ctx = await manage_components.wait_for_component(
                client, components=[self.previous_button, self.next_button]
            )
            if self.close_timer_task is None:
                self.close_timer_task = asyncio.create_task(
                    self.close_timer(button_ctx.edit_origin, timeout)
                )

            if button_ctx.author != ctx.author:
                await button_ctx.send(
                    "Sorry only the original command creator can use this button",
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

    async def close(self, edit_cmd: Callable[..., Awaitable[Any]]) -> None:
        self.next_button["disabled"] = True
        self.previous_button["disabled"] = True
        row = manage_components.create_actionrow(self.previous_button, self.next_button)

        await edit_cmd(compnents=[row])
        self.close_timer_task.cancel()

    async def close_timer(
        self, edit_cmd: Callable[..., Awaitable[Any]], timeout: int
    ) -> None:
        await asyncio.sleep(timeout)
        await self.close(edit_cmd)


class EmbedPaginator(Paginator):
    def __init__(
        self, embeds: List[discord.Embed], title_prefix: str = "Page: ", **kwargs
    ):
        super().__init__(num_pages=len(embeds), **kwargs)

        self.embeds = embeds
        self.title_prefix = title_prefix

    async def create_page_n(self, num: int) -> MESSAGE_KWARGS:
        embed = self.embeds[num - 1]
        embed.title = self.title_prefix + f"**{num}/{self.num_pages}**"

        return {"embed": embed}


class TextPaginator(Paginator):
    def __init__(
        self, pages: List[str], first_line_prefix: str = "**Page: ** ", **kwargs
    ):
        super().__init__(num_pages=len(pages), **kwargs)
        super().__init__(**kwargs)

        self.pages = pages
        self.first_line_prefix = first_line_prefix

    async def create_page_n(self, num: int) -> MESSAGE_KWARGS:
        page = self.pages[num - 1]
        page = f"{self.first_line_prefix} **{num}/{self.num_pages}**\n\n{page}"

        return {"content": page}

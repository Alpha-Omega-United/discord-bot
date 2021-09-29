from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import hikari

from bot import constants

if TYPE_CHECKING:
    from typing import Awaitable, Union

    import tanjun


def is_admin(member: hikari.Member) -> bool:
    roles = member.get_roles()
    return any(role.id == constants.ADMIN_ROLE_ID for role in roles)


async def wait_for_interaction(
    ctx: tanjun.SlashContext,
    message: hikari.Message,
    timeout: Union[int, float] = 60 * 5,
) -> hikari.ComponentInteraction:
    def predicate(event: hikari.InteractionCreateEvent) -> bool:
        inte = event.interaction
        return (
            isinstance(inte, hikari.ComponentInteraction)
            and inte.message.id == message.id
        )

    if ctx.events is None:
        raise TypeError("ctx.events is None")

    event = await ctx.events.wait_for(
        hikari.InteractionCreateEvent, timeout=timeout, predicate=predicate
    )
    return event.interaction  # type: ignore


@dataclass(frozen=True)
class ButtonInfo:
    label: str
    style: hikari.InteractiveButtonTypesT
    emoji: Union[
        hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType
    ] = hikari.UNDEFINED


async def confirmation_embed(
    ctx: tanjun.SlashContext,
    *,
    callback: Awaitable[None],
    embed: hikari.Embed,
    confirm_button: ButtonInfo,
    deny_button: ButtonInfo = ButtonInfo("Cancel", hikari.ButtonStyle.DANGER),
) -> None:
    confirm_button_id = "confirm"
    deny_button_id = "deny"

    buttons = (
        ctx.rest.build_action_row()
        .add_button(confirm_button.style, confirm_button_id)
        .set_label(confirm_button.label)
        .set_emoji(confirm_button.emoji)
        .add_to_container()
        .add_button(deny_button.style, deny_button_id)
        .set_label(deny_button.label)
        .set_emoji(deny_button.emoji)
        .add_to_container()
    )

    message = await ctx.respond(
        embed=embed, component=buttons, ensure_result=True
    )
    interaction = await wait_for_interaction(ctx, message)

    if embed.title is None:
        embed.title = ""

    if interaction.custom_id == confirm_button_id:
        await callback

        embed.color = constants.Colors.GREEN
        embed.title += ": DONE"
    else:
        embed.color = constants.Colors.RED
        embed.title += ": Canceld"

    # disable buttons
    buttons = (
        ctx.rest.build_action_row()
        .add_button(confirm_button.style, confirm_button_id)
        .set_label(confirm_button.label)
        .set_emoji(confirm_button.emoji)
        .set_is_disabled(True)
        .add_to_container()
        .add_button(deny_button.style, deny_button_id)
        .set_label(deny_button.label)
        .set_emoji(deny_button.emoji)
        .set_is_disabled(True)
        .add_to_container()
    )

    await interaction.create_initial_response(
        hikari.ResponseType.MESSAGE_UPDATE, embed=embed, component=buttons
    )

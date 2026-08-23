"""Test adapter for the message-routing acceptance contract.

This module is the only bridge between the acceptance suite and the
application. Tests should use ``route_message`` rather than importing the
application directly.
"""

from dataclasses import dataclass

from yt_dl_bot.message_router import MessageRouter


@dataclass(frozen=True)
class RoutingDecision:
    """A routing result expressed only in contract-level values."""

    action: str
    url: str | None


def route_message(
    *,
    author_is_bot: bool,
    content: object,
    channel_id: int,
    download_channel: int = 10,
    highlight_channel: int = 20,
    command_prefix: str | tuple[str, ...] = "!",
) -> RoutingDecision:
    """Return the externally observable routing decision for one message."""
    route = MessageRouter(
        command_prefix=command_prefix,
        download_channel=download_channel,
        highlight_channel=highlight_channel,
    ).route(
        author_is_bot=author_is_bot,
        content=content,
        channel_id=channel_id,
    )
    return RoutingDecision(action=str(route.action.value), url=route.url)

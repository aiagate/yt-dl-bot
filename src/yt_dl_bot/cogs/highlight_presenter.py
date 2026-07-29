"""Discord presentation helpers for YouTube highlight results."""

import datetime
from collections.abc import Iterable

from discord import Embed

from ..application_results import HighlightResult
from ..highlight import Highlight

DISCORD_FIELD_VALUE_LIMIT = 1024


def format_highlight_fields(
    highlights: Iterable[Highlight],
    max_length: int = DISCORD_FIELD_VALUE_LIMIT,
) -> tuple[str, ...]:
    """Format highlight links into values below Discord's field limit."""
    if max_length < 2:
        raise ValueError("max_length must be at least 2")

    field_limit = max_length - 1
    fields: list[str] = []
    current = ""
    for highlight in highlights:
        line = f"{datetime.timedelta(seconds=highlight.seconds)}\t{highlight.url}\n"
        line = line[:field_limit]
        if current and len(current + line) > field_limit:
            fields.append(current)
            current = ""
        current += line
    if current:
        fields.append(current)
    return tuple(fields) or ("does not get highlight"[:field_limit],)


def create_highlight_embed(result: HighlightResult) -> Embed:
    """Build the Discord embed for a structured highlight result."""
    embed = Embed(
        title=result.title,
        description=result.channel_name,
        color=0xFF0000,
    )
    embed.set_thumbnail(url=result.thumbnail_url)
    for field in format_highlight_fields(result.highlights):
        embed.add_field(name="highlight", value=field)
    embed.set_image(url="attachment://image.png")
    return embed

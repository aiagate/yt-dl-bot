"""Discord-independent helpers for formatting error reports."""

import traceback

DISCORD_FIELD_VALUE_LIMIT = 1024
# Five maximum-sized values plus their field names remain below Discord's
# 6,000-character aggregate limit for an embed.
DISCORD_FIELDS_PER_EMBED = 5
EMPTY_TRACEBACK_MESSAGE = "No traceback available."


def format_exception_traceback(error: BaseException) -> str:
    """Return the complete traceback for an exception."""
    return "".join(
        traceback.format_exception(type(error), error, error.__traceback__),
    )


def split_traceback_for_embeds(
    error_log: str,
    *,
    field_value_limit: int = DISCORD_FIELD_VALUE_LIMIT,
    fields_per_embed: int = DISCORD_FIELDS_PER_EMBED,
) -> tuple[tuple[str, ...], ...]:
    """Split a traceback into embed-sized batches without losing text."""
    if field_value_limit <= 0:
        raise ValueError("field_value_limit must be positive")
    if fields_per_embed <= 0:
        raise ValueError("fields_per_embed must be positive")

    text = error_log or EMPTY_TRACEBACK_MESSAGE
    chunks = tuple(
        text[index : index + field_value_limit] for index in range(0, len(text), field_value_limit)
    )
    return tuple(
        chunks[index : index + fields_per_embed]
        for index in range(0, len(chunks), fields_per_embed)
    )

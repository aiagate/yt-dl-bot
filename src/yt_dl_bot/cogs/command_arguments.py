"""Discord command argument converters and user-facing error responses."""

from typing import Any

from discord.ext import commands

from ..url_validation import validate_service_url


class ServiceURLConverter(commands.Converter[str]):
    """Validate a URL for the service selected by a concrete converter."""

    service: str

    async def convert(
        self,
        ctx: commands.Context[Any],
        argument: str,
    ) -> str:
        del ctx
        try:
            return validate_service_url(argument, self.service)
        except ValueError as error:
            raise commands.BadArgument(
                f"Invalid {self.service} URL",
            ) from error


class YouTubeURL(ServiceURLConverter):
    service = "youtube"


class TwitchURL(ServiceURLConverter):
    service = "twitch"


async def handle_url_argument_error(
    ctx: commands.Context[Any],
    error: commands.CommandError,
    *,
    usage: str,
) -> bool:
    """Reply to expected argument errors and return whether handled."""
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(f"Error: URL is required. Usage: {usage}")
        return True
    if isinstance(error, commands.TooManyArguments):
        await ctx.reply(f"Error: too many arguments. Usage: {usage}")
        return True
    if isinstance(error, commands.BadArgument):
        await ctx.reply(f"Error: {error}")
        return True
    return False

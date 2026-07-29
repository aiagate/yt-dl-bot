# ---standard library---
import asyncio
from typing import TYPE_CHECKING, cast

# ---third party library---
from discord.ext import commands

from ..cancellation import to_thread_cancellable

# ---local library---
from ..video_download_service import TwitchStreamOffline
from .command_arguments import (
    TwitchURL,
    handle_url_argument_error,
)

if TYPE_CHECKING:
    from ..discord_bot_main import DownloadBot


class TwitchCog(commands.Cog):
    def __init__(self, bot: "DownloadBot") -> None:
        self.bot = bot
        self.settings = bot.settings
        self.download_service = bot.services.twitch_download

    @commands.group(name="twitch")
    async def twitch_cog(self, ctx: commands.Context["DownloadBot"]) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send("Error: missing option")

    # discord.py's Group.command typing loses converter callback parameters.
    @twitch_cog.command(name="download", ignore_extra=False)  # type: ignore[arg-type]
    async def download_video(
        self,
        ctx: commands.Context["DownloadBot"],
        url: str = commands.parameter(converter=TwitchURL),
    ) -> None:
        try:
            result = await asyncio.to_thread(
                self.download_service.check,
                url,
            )
        except TwitchStreamOffline:
            await ctx.reply("このチャンネルでライブは始まっていません。")
            return

        await ctx.reply(result)

        download_result = await to_thread_cancellable(
            self.download_service.download,
            url,
        )
        self.bot.logger.info("Download Success!")
        command = self.bot.get_command("send_video_output_log")
        if command is None:
            raise RuntimeError("send_video_output_log command is not loaded")
        cog_command = cast(commands.Command[commands.Cog, ..., object], command)
        await ctx.invoke(cog_command, result=download_result)

    @download_video.error
    async def download_video_error(
        self,
        ctx: commands.Context["DownloadBot"],
        error: commands.CommandError,
    ) -> None:
        if await handle_url_argument_error(
            ctx,
            error,
            usage="twitch download <url>",
        ):
            return
        command = self.bot.get_command("send_error_log")
        if command is None:
            raise RuntimeError("send_error_log command is not loaded")
        cog_command = cast(commands.Command[commands.Cog, ..., object], command)
        await ctx.invoke(cog_command, error)


async def setup(bot: "DownloadBot") -> None:
    await bot.add_cog(TwitchCog(bot))

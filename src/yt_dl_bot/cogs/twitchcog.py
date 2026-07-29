# ---standard library---
import asyncio

# ---third party library---
from discord.ext import commands

from ..cancellation import to_thread_cancellable

# ---local library---
from ..video_download_service import TwitchStreamOffline
from .command_arguments import (
    TwitchURL,
    handle_url_argument_error,
)


class TwitchCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = bot.settings
        self.download_service = bot.services.twitch_download

    @commands.group(name="twitch")
    async def twitch_cog(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Error: missing option")

    @twitch_cog.command(name="download", ignore_extra=False)
    async def download_video(self, ctx, url: TwitchURL):
        try:
            result = await asyncio.to_thread(
                self.download_service.check,
                url,
            )
        except TwitchStreamOffline:
            await ctx.reply("このチャンネルでライブは始まっていません。")
            return

        await ctx.reply(result)

        result = await to_thread_cancellable(
            self.download_service.download,
            url,
        )
        self.bot.logger.info("Download Success!")
        await ctx.invoke(
            self.bot.get_command("send_video_output_log"),
            result=result,
        )

    @download_video.error
    async def download_video_error(self, ctx, error):
        if await handle_url_argument_error(
            ctx,
            error,
            usage="twitch download <url>",
        ):
            return
        await ctx.invoke(self.bot.get_command("send_error_log"), error)


async def setup(bot):
    await bot.add_cog(TwitchCog(bot))

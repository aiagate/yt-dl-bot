# ---standard library---
import asyncio

# ---third party library---
from discord import Embed, File
from discord.ext import commands

# ---local library---
from ..cancellation import to_thread_cancellable
from .command_arguments import (
    YouTubeURL,
    handle_url_argument_error,
)


class YouTubeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = bot.settings
        self.download_service = bot.services.youtube_download
        self.highlight_service = bot.services.youtube_highlight

    @commands.group(name="youtube")
    async def youtube_cog(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Error: missing option")

    @youtube_cog.command(name="download", ignore_extra=False)
    async def download_video(self, ctx, url: YouTubeURL):
        text = await asyncio.to_thread(self.download_service.check, url)

        for t in text.split("\n"):
            self.bot.logger.info(t)
        await ctx.reply(text)

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
            usage="youtube download <url>",
        ):
            return
        await ctx.invoke(self.bot.get_command("send_error_log"), error)

    @youtube_cog.command(name="highlight", ignore_extra=False)
    async def get_highlight(self, ctx, url: YouTubeURL):
        await ctx.reply("Starting get highlight...")

        result = await asyncio.to_thread(
            self.highlight_service.create,
            url,
        )
        graph_image = result.graph_image
        self.bot.logger.debug(graph_image)
        file = await asyncio.to_thread(
            File,
            graph_image,
            filename="image.png",
        )

        embed = Embed(
            title=result.title,
            description=result.channel_name,
            color=0xFF0000,
        )
        embed.set_thumbnail(url=result.thumbnail_url)
        for field in result.highlight_fields:
            embed.add_field(name="highlight", value=field)
        embed.set_image(url="attachment://image.png")

        await ctx.invoke(
            self.bot.get_command("send_highlight_output_log"),
            file,
            embed,
        )
        await asyncio.to_thread(
            self.highlight_service.archive_graph,
            graph_image,
        )

    @get_highlight.error
    async def get_highlight_error(self, ctx, error):
        if await handle_url_argument_error(
            ctx,
            error,
            usage="youtube highlight <url>",
        ):
            return
        await ctx.invoke(self.bot.get_command("send_error_log"), error)


async def setup(bot):
    await bot.add_cog(YouTubeCog(bot))


# Compatibility alias. New code should use YouTubeCog.
YoutubeCog = YouTubeCog

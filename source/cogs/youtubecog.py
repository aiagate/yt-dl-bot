#! ./.venv/bin/python

# ---standard library---
import asyncio

# ---third party library---
from discord import Embed, File
from discord.ext import commands

# ---local library---
from cancellation import to_thread_cancellable
from url_validation import validate_service_url


class YoutubeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = bot.settings
        self.download_service = bot.services.youtube_download
        self.highlight_service = bot.services.youtube_highlight

    @staticmethod
    def parse_url(url):
        return validate_service_url(url, 'youtube')

    @commands.group(name='youtube')
    async def youtube_cog(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Error: missing option')

    @youtube_cog.command(name='download')
    async def download_video(self, ctx, *args, **kwargs):
        # url = args[0]
        url = self.parse_url(args[0])

        text = await asyncio.to_thread(self.download_service.check, url)

        for t in text.split('\n'):
            self.bot.logger.info(t)
        await ctx.reply(text)

        result = await to_thread_cancellable(
            self.download_service.download,
            url,
        )
        self.bot.logger.info('Download Success!')
        await ctx.invoke(
            self.bot.get_command('send_video_output_log'),
            info=result.info,
            url=result.url,
        )
        return

    @download_video.error
    async def download_video_error(self, ctx, error):
        await ctx.invoke(self.bot.get_command('send_error_log'), error)

    @youtube_cog.command(name='highlight')
    async def get_highlight(self, ctx, *args, **kwargs):
        url = self.parse_url(args[0])

        await ctx.reply('Starting get highlight...')

        result = await asyncio.to_thread(
            self.highlight_service.create,
            url,
        )
        graph_image = result.graph_image
        self.bot.logger.debug(graph_image)
        file = await asyncio.to_thread(
            File,
            graph_image,
            filename='image.png',
        )

        embed = Embed(
            title=result.title,
            description=result.channel_name,
            color=0xff0000,
        )
        embed.set_thumbnail(url=result.thumbnail_url)
        for field in result.highlight_fields:
            embed.add_field(name="highlight", value=field)
        embed.set_image(url="attachment://image.png")

        await ctx.invoke(
            self.bot.get_command('send_highlight_output_log'),
            file,
            embed,
        )
        await asyncio.to_thread(
            self.highlight_service.archive_graph,
            graph_image,
        )
        return

    @get_highlight.error
    async def get_highlight_error(self, ctx, error):
        await ctx.invoke(self.bot.get_command('send_error_log'), error)


async def setup(bot):
    await bot.add_cog(YoutubeCog(bot))

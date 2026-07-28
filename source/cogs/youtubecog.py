#! ./.venv/bin/python

# ---standard library---
import datetime
import importlib
import os
import shutil
from functools import partial

# ---third party library---
from discord import Embed, File
from discord.ext import commands

# ---local library---
import youtubemodule
import chatdatamodule
import property
from url_validation import validate_service_url


class YoutubeCog(commands.Cog):
    def __init__(self, bot):
        importlib.reload(importlib)
        importlib.reload(youtubemodule)
        importlib.reload(chatdatamodule)
        importlib.reload(property)
        self.bot = bot

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

        ytm = youtubemodule.YoutubeModule()

        fn = partial(ytm.data_check, url=url, ydl_ops={})
        try:
            text = await self.bot.loop.run_in_executor(None, fn)
        except Exception as e:
            await ctx.invoke(self.bot.get_command('send_error_log'), e)
            raise e

        for t in text.split('\n'):
            self.bot.logger.info(t)
        await ctx.reply(text)

        fn = partial(ytm.download_video, url=url)
        try:
            info = await self.bot.loop.run_in_executor(None, fn)
        except Exception as e:
            await ctx.invoke(self.bot.get_command('send_error_log'), e)
            raise e
        self.bot.logger.info('Download Success!')
        try:
            await ctx.invoke(self.bot.get_command('send_video_output_log'), info=info, url=url)
        except Exception as e:
            await ctx.invoke(self.bot.get_command('send_error_log'), e)
            raise e
        return

    @download_video.error
    async def download_video_error(self, ctx, error):
        # self.bot.logger.info(error)
        await ctx.invoke(self.bot.get_command('send_error_log'), error)

    @youtube_cog.command(name='highlight')
    async def get_highlight(self, ctx, *args, **kwargs):
        url = self.parse_url(args[0])

        await ctx.reply('Starting get highlight...')

        ytm = youtubemodule.YoutubeModule()
        video_id = ytm.get_videoid(url=url)
        video_info = ytm.get_info(url=url)

        cdm = chatdatamodule.ChatDataModule(video_id=video_id)
        fn = partial(cdm.get_highlight)
        try:
            highlight_urls = await self.bot.loop.run_in_executor(None, fn)
        except Exception as e:
            await ctx.invoke(self.bot.get_command('send_error_log'), e)
            raise e
        try:
            video_info.setdefault('fulltitle', video_info['title'])
            channel_name = video_info['channel']
            title = video_info['fulltitle']
            thumbnail_url = video_info['thumbnail']

            graph_image = cdm.image_path
            self.bot.logger.debug(graph_image)
            file = File(graph_image, filename='image.png')

            embed = Embed(
                title=title, description=channel_name, color=0xff0000)
            embed.set_thumbnail(url=thumbnail_url)
            highlight_url_text = ''
            for highlight in highlight_urls:
                if len(highlight_url_text + str(datetime.timedelta(seconds=highlight[0])) + '\t' + highlight[1] + '\n') < 1024:
                    highlight_url_text = highlight_url_text + str(datetime.timedelta(seconds=highlight[0])) + '\t' + highlight[1] + '\n'
                else:
                    embed.add_field(name="highlight", value=highlight_url_text)
                    highlight_url_text = str(datetime.timedelta(seconds=highlight[0])) + '\t' + highlight[1] + '\n'
            if highlight_url_text != '':
                embed.add_field(name="highlight", value=highlight_url_text)
            else:
                embed.add_field(name="highlight", value="does not get highlight")
            embed.set_image(url="attachment://image.png")

            await ctx.invoke(self.bot.get_command('send_highlight_output_log'), file, embed)
        except Exception as e:
            await ctx.invoke(self.bot.get_command('send_error_log'), e)
            raise e

        try:
            out_path = property.GRAPH_SAVE_PATH
            if not os.path.exists(out_path):
                os.mkdir(out_path)
            shutil.move(graph_image, out_path)
        except Exception as e:
            await ctx.invoke(self.bot.get_command('send_error_log'), e)
            raise e
        return


async def setup(bot):
    await bot.add_cog(YoutubeCog(bot))

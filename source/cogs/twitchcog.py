#! ./.venv/bin/python

# ---standard library---
from asyncio.log import logger
import datetime
import importlib
import os
import requests
import shutil
from functools import partial

# ---third party library---
from discord import Embed, File
from discord.ext import commands

# ---local library---
import db_connect
import ytdlpmodule
import chatdatamodule
import chatdataextractor
import youtubeapi
import property


class TwitchCog(commands.Cog):
    def __init__(self, bot):
        importlib.reload(importlib)
        importlib.reload(db_connect)
        importlib.reload(ytdlpmodule)
        importlib.reload(chatdatamodule)
        importlib.reload(chatdataextractor)
        importlib.reload(youtubeapi)
        importlib.reload(property)
        self.bot = bot

    @staticmethod
    def parse_url(url):
        try:
            url = requests.get(url).url.split('&')[0]
            return url
        except Exception as e:
            raise e

    @commands.group(name='twitch')
    async def twitch_cog(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Error: missing option')

    @twitch_cog.command(name='download')
    async def download_video(self, ctx, *args, **kwargs):
        url = self.parse_url(args[0])

        ytm = ytdlpmodule.YtdlpModule()

        fn = partial(ytm.data_check, url=url, ydl_ops={})
        try:
            result = await self.bot.loop.run_in_executor(None, fn)
        except Exception as e:
            error = str(e.exc_info[1])
            if 'The channel is not currently live' in error:
                await ctx.reply('このチャンネルでライブは始まっていません。')
                return
            await ctx.invoke(self.bot.get_command('send_error_log'), e)
            raise e

        await ctx.reply(result)

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
        await ctx.invoke(self.bot.get_command('send_error_log'), error)

def setup(bot):
    return bot.add_cog(TwitchCog(bot))

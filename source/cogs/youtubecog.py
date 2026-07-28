#! ./.venv/bin/python

# ---standard library---
import argparse
from ast import arg
from asyncio.log import logger
import datetime
import importlib
import os
import re
import requests
import shutil
from functools import partial

# ---third party library---
from discord import Embed, File
from discord.ext import commands

# ---local library---
import db_connect
import youtubemodule
import chatdatamodule
import chatdataextractor
import youtubeapi
import property


class YoutubeCog(commands.Cog):
    def __init__(self, bot):
        importlib.reload(importlib)
        importlib.reload(db_connect)
        importlib.reload(youtubemodule)
        importlib.reload(chatdatamodule)
        importlib.reload(chatdataextractor)
        importlib.reload(youtubeapi)
        importlib.reload(property)
        self.bot = bot

    @staticmethod
    def parse_url(url):
        try:
            url = requests.get(url).url.split('&')[0]
            # parsed_url = urllib.parse.urlparse(url)
            return url
        except Exception as e:
            raise e

    @commands.group(name='youtube')
    async def youtube_cog(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Error: missing option')

    @youtube_cog.command(name='getinfo')
    async def get_videoinfo(self, ctx, *args, **kwargs):
        if len(args) == 0:
            await ctx.send('Error: need URLs!')
            return

        for url in args:
            with youtube_dl.YoutubeDL() as ydl:
                info = ydl.extract_info(url, download=False)
            self.bot.logger.info(info)
            await ctx.send(info)

    @get_videoinfo.error
    async def get_videoinfo_error(self, ctx, error):
        self.bot.logger.info(error)
        await ctx.invoke(self.bot.get_command('send_error_log'), error)

    @youtube_cog.command(name='liveinfo')
    async def get_liveinfo(self, ctx, *args, **kwargs):
        if len(args) == 0:
            await ctx.send('Error: need URLs!')
            return

        for index, url in enumerate(args):
            info = self.ytd_info(url)
            # self.bot.logger.info(info)
            await ctx.send(info)

    @get_liveinfo.error
    async def get_liveinfo_error(self, ctx, error):
        self.bot.logger.info(error)
        await ctx.invoke(self.bot.get_command('send_error_log'), error)

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

        # コメント処理
        '''
        cvm = chatviewmodule.ChatViewModule(ytm.get_videoid(url=url), date)
        fn = partial(cvm.cut_movie, file_path=outpath, title=title, date=date, pool=pool)
        try:
            info = await self.bot.loop.run_in_executor(None, fn)
        except Exception as e:
            await ctx.invoke(self.bot.get_command('send_error_log'), e)
            raise e
        '''

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

        cdm = chatdatamodule.ChatDataModule(video_id=video_id, starttime=video_info['release_timestamp'])
        fn = partial(cdm.get_highlight)
        try:
            highlight_urls = await self.bot.loop.run_in_executor(None, fn)
        except Exception as e:
            await ctx.invoke(self.bot.get_command('send_error_log'), e)
            raise e
        # '''

        # print(len(highlight_url))
        # res = '\n'.join(highlight_url)
        # await ctx.invoke(self.bot.get_command('echo'), res)

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

    @youtube_cog.group(name='search')
    async def chat_search(self, ctx):
        cde = chatdataextractor.ChatDataExtractor()
        cde.table_name = 'chat_data_petit'
        if ctx.invoked_subcommand is None:
            await ctx.send('Error: missing option')

    @chat_search.command(name='whitetails')
    async def search_whitetails(self, ctx, *args):
        keyword = args[0]
        await ctx.reply('Starting search chat data...')

        cde = chatdataextractor.ChatDataExtractor()
        cde.table_name = 'yt_chatdata'
        fn = partial(cde.search_video_keyword, keyword)
        try:
            result = await self.bot.loop.run_in_executor(None, fn)
        except Exception as e:
            await ctx.invoke(self.bot.get_command('send_error_log'), e)
            raise e
        if (len(result) == 0):
            await ctx.reply(f'Not Found [{keyword}]')
            return
        await ctx.reply(f'Found {len(result)} Videos')

        for r in result:
            video_id = r[0]

            fn = partial(cde.extract_from_keyword, video_id, keyword)
            try:
                result2 = await self.bot.loop.run_in_executor(None, fn)
            except Exception as e:
                await ctx.invoke(self.bot.get_command('send_error_log'), e)
                raise e

            embed = Embed(title=f'Search [{keyword}] https://youtu.be/{video_id}',color=0xff0000)
            embed.set_thumbnail(url=f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg")
            urls = ''
            if (len(result2) == 0):
                await ctx.reply('data was empty')
                continue
            for url in result2:
                if len(urls + url) < 1024:
                    urls += f'{url}\n'
                else:
                    embed.add_field(name='search result', value=urls)
                    urls = ''
            if (urls != ''):
                embed.add_field(name='search result', value=urls)
                await ctx.invoke(self.bot.get_command('send_search_output_log'), embed)
        await ctx.reply(f'Search Finish!')

    @chat_search.command(name='petit')
    async def search_petit(self, ctx, *args):

        keyword = args[0]
        try:
            minscore = int(args[1])
        except:
            minscore = 0
        await ctx.reply('Starting search chat data...')

        cde = chatdataextractor.ChatDataExtractor()
        cde.table_name = 'chat_data_petit'
        fn = partial(cde.search_video_keyword, keyword)
        try:
            result = await self.bot.loop.run_in_executor(None, fn)
        except Exception as e:
            await ctx.invoke(self.bot.get_command('send_error_log'), e)
            raise e
        if (len(result) == 0):
            await ctx.reply(f'Not Found [{keyword}]')
            return
        await ctx.reply(f'Found {len(result)} Videos')
        for r in result:
            video_id = r[0]

            fn = partial(cde.extract_from_keyword, video_id, keyword, minscore)
            try:
                result2 = await self.bot.loop.run_in_executor(None, fn)
            except Exception as e:
                await ctx.invoke(self.bot.get_command('send_error_log'), e)
                raise e

            embed = Embed(title=f'Search [{keyword}] https://youtu.be/{video_id}',color=0xff0000)
            embed.set_thumbnail(url=f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg")
            urls = ''
            # if (len(result2) == 0):
            #     await ctx.reply('data was empty')
            #     continue
            for url in result2:
                if len(urls + url) < 1024:
                    urls += f'{url}\n'
                else:
                    embed.add_field(name='search result', value=urls)
                    urls = ''
            if (urls != ''):
                embed.add_field(name='search result', value=urls)
                await ctx.invoke(self.bot.get_command('send_search_output_log'), embed)
        await ctx.reply(f'Search Finished!')
def setup(bot):
    return bot.add_cog(YoutubeCog(bot))

#! ./.venv/bin/python

# ---standard library---
import requests
import urllib

# ---third party library---
from discord.ext import commands

# ---local library---
import property


class MainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def is_url(text):
        try:
            url = requests.get(text)
            return True
        except Exception as e:
            return False

    @staticmethod
    def get_domain(self, url):
        try:
            url = requests.get(url).url.split('&')[0]
            parsed_url = urllib.parse.urlparse(url)
            return parsed_url.netloc
        except Exception as e:
            raise e

    @commands.Cog.listener(name='on_message')
    async def on_message(self, message):
        # Bot同士による会話を制限
        if message.author.bot:
            return
        # コマンドの場合処理をしない
        elif '!' in message.content:
            return
        elif self.is_url(message.content):
            if self.get_domain(self, message.content) == 'www.youtube.com':
                if message.channel.id == property.HIGHLIGHT_CHANNEL:
                    message.content = '!youtube highlight ' + message.content
                elif message.channel.id == property.DOWNLOAD_CHANNEL:
                    message.content = '!youtube download ' + message.content
            elif self.get_domain(self, message.content) == 'www.twitch.tv':
                if message.channel.id == property.HIGHLIGHT_CHANNEL:
                    message.content = '!twitch highlight ' + message.content
                elif message.channel.id == property.DOWNLOAD_CHANNEL:
                    message.content = '!twitch download ' + message.content
        elif message.channel.id == property.SEARCH_CHANNEL:
            message.content = '!youtube search whitetails ' + message.content
        else:
            return

        self.bot.logger.info(message.content)
        await self.bot.process_commands(message)
        return


def setup(bot):
    return bot.add_cog(MainCog(bot))

#! ./.venv/bin/python

# ---third party library---
from discord.ext import commands

# ---local library---
from url_validation import identify_service


class MainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = bot.settings

    @staticmethod
    def is_url(text):
        return identify_service(text) is not None

    @staticmethod
    def get_service(url):
        return identify_service(url)

    @commands.Cog.listener(name='on_message')
    async def on_message(self, message):
        # Bot同士による会話を制限
        if message.author.bot:
            return
        # コマンドの場合処理をしない
        elif '!' in message.content:
            return
        elif self.is_url(message.content):
            service = self.get_service(message.content)
            if service == 'youtube':
                if message.channel.id == self.settings.HIGHLIGHT_CHANNEL:
                    message.content = '!youtube highlight ' + message.content
                elif message.channel.id == self.settings.DOWNLOAD_CHANNEL:
                    message.content = '!youtube download ' + message.content
            elif service == 'twitch':
                if message.channel.id == self.settings.DOWNLOAD_CHANNEL:
                    message.content = '!twitch download ' + message.content
        else:
            return

        self.bot.logger.info(message.content)
        await self.bot.process_commands(message)
        return


async def setup(bot):
    await bot.add_cog(MainCog(bot))

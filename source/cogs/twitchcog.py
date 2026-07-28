#! ./.venv/bin/python

# ---standard library---
import asyncio

# ---third party library---
from discord.ext import commands

# ---local library---
from application_services import TwitchStreamOffline
from cancellation import to_thread_cancellable
from url_validation import validate_service_url


class TwitchCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = bot.settings
        self.download_service = bot.services.twitch_download

    @staticmethod
    def parse_url(url):
        return validate_service_url(url, 'twitch')

    @commands.group(name='twitch')
    async def twitch_cog(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Error: missing option')

    @twitch_cog.command(name='download')
    async def download_video(self, ctx, *args, **kwargs):
        url = self.parse_url(args[0])

        try:
            result = await asyncio.to_thread(
                self.download_service.check,
                url,
            )
        except TwitchStreamOffline:
            await ctx.reply('このチャンネルでライブは始まっていません。')
            return

        await ctx.reply(result)

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

async def setup(bot):
    await bot.add_cog(TwitchCog(bot))

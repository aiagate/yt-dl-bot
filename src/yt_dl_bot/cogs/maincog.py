import asyncio
from typing import TYPE_CHECKING, cast

import discord
from discord.ext import commands

from ..cancellation import to_thread_cancellable
from ..discord_notification_delivery import DiscordNotificationDelivery
from ..message_router import MessageAction, MessageRouter
from ..video_download_service import TwitchStreamOffline

if TYPE_CHECKING:
    from ..discord_bot_main import DownloadBot


class MainCog(commands.Cog):
    def __init__(self, bot: "DownloadBot") -> None:
        self.bot = bot
        self.settings = bot.settings
        self.router = MessageRouter(
            command_prefix=cast(str | tuple[str, ...], bot.command_prefix),
            download_channel=self.settings.DOWNLOAD_CHANNEL,
        )
        self.notifications = DiscordNotificationDelivery(bot)

    @commands.Cog.listener(name="on_message")
    async def on_message(self, message: discord.Message) -> None:
        route = self.router.route(
            author_is_bot=message.author.bot,
            content=message.content,
            channel_id=message.channel.id,
        )
        if route.action in {MessageAction.IGNORE, MessageAction.COMMAND} or route.url is None:
            return

        is_youtube = route.action is MessageAction.YOUTUBE_DOWNLOAD
        service = (
            self.bot.services.youtube_download if is_youtube else self.bot.services.twitch_download
        )
        ctx = await self.bot.get_context(message)
        try:
            try:
                result = await asyncio.to_thread(service.check, route.url)
            except TwitchStreamOffline:
                await ctx.reply("このチャンネルでライブは始まっていません。")
                return
            if is_youtube:
                for line in result.split("\n"):
                    self.bot.logger.info(line)
            await ctx.reply(result)
            downloaded = await to_thread_cancellable(service.download, route.url)
            self.bot.logger.info("Download Success!")
            await self.notifications.send_download_result(downloaded)
        except Exception as error:
            await self.notifications.report_error(ctx, error)


async def setup(bot: "DownloadBot") -> None:
    await bot.add_cog(MainCog(bot))

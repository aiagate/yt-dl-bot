from typing import TYPE_CHECKING, cast

import discord

# ---third party library---
from discord.ext import commands

# ---local library---
from ..message_router import MessageAction, MessageRouter

if TYPE_CHECKING:
    from ..discord_bot_main import DownloadBot


class MainCog(commands.Cog):
    def __init__(self, bot: "DownloadBot") -> None:
        self.bot = bot
        self.settings = bot.settings
        command_prefix = cast(str | tuple[str, ...], bot.command_prefix)
        self.router = MessageRouter(
            command_prefix=command_prefix,
            download_channel=self.settings.DOWNLOAD_CHANNEL,
            highlight_channel=self.settings.HIGHLIGHT_CHANNEL,
        )

    @commands.Cog.listener(name="on_message")
    async def on_message(self, message: discord.Message) -> None:
        route = self.router.route(
            author_is_bot=message.author.bot,
            content=message.content,
            channel_id=message.channel.id,
        )
        if route.action in {MessageAction.IGNORE, MessageAction.COMMAND}:
            # Bot.on_message owns normal command processing. Calling
            # process_commands from this additional listener would run it twice.
            return

        command_name = route.action.command_name
        if command_name is None:
            return
        command = self.bot.get_command(command_name)
        if command is None:
            self.bot.logger.error(
                "Automatic route command is not loaded: %s",
                command_name,
            )
            return
        cog_command = cast(commands.Command[commands.Cog, ..., object], command)

        self.bot.logger.info(
            "Automatic route: %s",
            command_name,
        )
        ctx = await self.bot.get_context(message)
        await ctx.invoke(cog_command, route.url)


async def setup(bot: "DownloadBot") -> None:
    await bot.add_cog(MainCog(bot))

# ---third party library---
from discord.ext import commands

# ---local library---
from ..message_router import MessageAction, MessageRouter


class MainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = bot.settings
        self.router = MessageRouter(
            command_prefix=bot.command_prefix,
            download_channel=self.settings.DOWNLOAD_CHANNEL,
            highlight_channel=self.settings.HIGHLIGHT_CHANNEL,
        )

    @commands.Cog.listener(name="on_message")
    async def on_message(self, message):
        route = self.router.route(
            author_is_bot=message.author.bot,
            content=message.content,
            channel_id=message.channel.id,
        )
        if route.action in {MessageAction.IGNORE, MessageAction.COMMAND}:
            # Bot.on_message owns normal command processing. Calling
            # process_commands from this additional listener would run it twice.
            return

        command = self.bot.get_command(route.action.command_name)
        if command is None:
            self.bot.logger.error(
                "Automatic route command is not loaded: %s",
                route.action.command_name,
            )
            return

        self.bot.logger.info(
            "Automatic route: %s",
            route.action.command_name,
        )
        ctx = await self.bot.get_context(message)
        await ctx.invoke(command, route.url)


async def setup(bot):
    await bot.add_cog(MainCog(bot))

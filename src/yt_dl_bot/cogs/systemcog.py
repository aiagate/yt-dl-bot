# ---standard library---
import asyncio
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, cast

# ---third party library---
from discord import Embed, File, TextChannel
from discord.ext import commands

from ..application_results import DownloadResult
from ..error_reporting import (
    format_exception_traceback,
    sanitize_discord_error_report,
    split_traceback_for_embeds,
)

if TYPE_CHECKING:
    from ..discord_bot_main import DownloadBot


def _extension_names(
    arguments: Iterable[str],
    initial_extensions: Sequence[str],
) -> list[str]:
    """Expand ``all`` and remove duplicate extension names."""
    names = []
    for argument in arguments:
        extensions = initial_extensions if argument == "all" else ("yt_dl_bot.cogs." + argument,)
        for extension in extensions:
            if extension not in names:
                names.append(extension)
    return names


class SystemCog(commands.Cog):
    def __init__(self, bot: "DownloadBot") -> None:
        self.bot = bot
        self.settings = bot.settings

    @commands.group(name="system")
    async def botsystem(self, ctx: commands.Context["DownloadBot"]) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send("Error: missing option")

    # discord.py's Group.command typing loses the callback parameters for nested commands.
    @botsystem.command(name="close")  # type: ignore[arg-type]
    @commands.is_owner()
    async def botsystem_close(self, ctx: commands.Context["DownloadBot"]) -> None:
        channel = cast(TextChannel, self.bot.get_channel(self.settings.LOG_CHANNEL))
        await channel.send("Bot System Will Be Shutdown...")
        await asyncio.sleep(3)
        await self.bot.close()

    @commands.group(name="cog")
    async def cogs(self, ctx: commands.Context["DownloadBot"]) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send("Error: missing option")

    @cogs.group(name="reload")  # type: ignore[arg-type]
    @commands.is_owner()
    async def cogs_reload(
        self,
        ctx: commands.Context["DownloadBot"],
        *args: str,
        **kwargs: object,
    ) -> None:
        if len(args) == 0:
            await ctx.send("Error: missing cog name operand")
            return

        for extension in _extension_names(
            args,
            self.settings.INITIAL_EXTENSIONS,
        ):
            await self.bot.reload_extension(extension)
            await ctx.send("Success: " + extension + " is Reloaded.")

    @cogs_reload.error
    async def cogs_reload_error(
        self,
        ctx: commands.Context["DownloadBot"],
        error: commands.CommandError,
    ) -> None:
        await ctx.send("Error: " + str(error))

    @cogs.group(name="load")  # type: ignore[arg-type]
    @commands.is_owner()
    async def cogs_load(
        self,
        ctx: commands.Context["DownloadBot"],
        *args: str,
        **kwargs: object,
    ) -> None:
        if len(args) == 0:
            await ctx.send("Error: missing cog name operand")
            return

        for extension in _extension_names(
            args,
            self.settings.INITIAL_EXTENSIONS,
        ):
            await self.bot.load_extension(extension)
            await ctx.send("Success: " + extension + " is Loaded.")

    @cogs_load.error
    async def cogs_load_error(
        self,
        ctx: commands.Context["DownloadBot"],
        error: commands.CommandError,
    ) -> None:
        await ctx.send("Error: " + str(error))

    @cogs.group(name="unload")  # type: ignore[arg-type]
    @commands.is_owner()
    async def cogs_unload(
        self,
        ctx: commands.Context["DownloadBot"],
        *args: str,
        **kwargs: object,
    ) -> None:
        if len(args) == 0:
            await ctx.send("Error: missing cog name operand")
            return

        force_option = "-f" in args
        targets = tuple(argument for argument in args if argument != "-f")
        if not targets:
            await ctx.send("Error: missing cog name operand")
            return
        if "all" in targets and not force_option:
            await ctx.send("Error: can't unload. (force unload : -f)")
            return
        if "systemcog" in targets and not force_option:
            await ctx.send("Error: systemcog can't unload. (force unload : -f)")
            return

        for extension in _extension_names(
            targets,
            self.settings.INITIAL_EXTENSIONS,
        ):
            await self.bot.unload_extension(extension)
            await ctx.send("Success: " + extension + " is Unloaded.")

    @cogs_unload.error
    async def cogs_unload_error(
        self,
        ctx: commands.Context["DownloadBot"],
        error: commands.CommandError,
    ) -> None:
        await ctx.send("Error: " + str(error))

    @commands.command(enabled=False)
    async def send_log(
        self,
        ctx: commands.Context["DownloadBot"],
        *args: str,
        **kwargs: object,
    ) -> None:
        channel = cast(TextChannel, self.bot.get_channel(self.settings.LOG_CHANNEL))
        await channel.send("``" + "\n".join(args) + "``")

    @commands.command(enabled=False)
    async def send_error_log(
        self,
        ctx: commands.Context["DownloadBot"],
        error: BaseException,
        *args: object,
        **kwargs: object,
    ) -> None:
        log_channel = cast(TextChannel, self.bot.get_channel(self.settings.LOG_CHANNEL))
        error_log = format_exception_traceback(error)

        # Persist the complete traceback before attempting Discord I/O. This
        # ensures a failed notification never hides the original error.
        self.bot.logger.error(error_log)
        discord_error_log = sanitize_discord_error_report(error_log)

        await ctx.reply("Error: Check " + log_channel.mention)

        field_number = 1
        for field_batch in split_traceback_for_embeds(discord_error_log):
            embed = Embed()
            for field_value in field_batch:
                embed.add_field(
                    name=f"Traceback {field_number}",
                    value=field_value,
                    inline=False,
                )
                field_number += 1
            await log_channel.send(embed=embed)

    @commands.command(enabled=False)
    async def send_video_output_log(
        self,
        ctx: commands.Context["DownloadBot"],
        result: DownloadResult,
    ) -> None:
        channel = cast(TextChannel, self.bot.get_channel(self.settings.VIDEO_OUTPUT_CHANNEL))
        await channel.send(
            "**Download Success : **" + result.title + "\n" + result.source_url,
        )

    @commands.command(enabled=False)
    async def send_highlight_output_log(
        self,
        ctx: commands.Context["DownloadBot"],
        file: File,
        embed: Embed,
    ) -> None:
        channel = cast(TextChannel, self.bot.get_channel(self.settings.HIGHLIGHT_OUTPUT_CHANNEL))
        await channel.send(file=file, embed=embed)


async def setup(bot: "DownloadBot") -> None:
    await bot.add_cog(SystemCog(bot))

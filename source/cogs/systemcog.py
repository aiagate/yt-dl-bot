#! ./.venv/bin/python

# ---standard library---
import asyncio

# ---third party library---
from discord import Embed
from discord.ext import commands

from error_reporting import (
    format_exception_traceback,
    split_traceback_for_embeds,
)


def _extension_names(arguments, initial_extensions):
    """Expand ``all`` and remove duplicate extension names."""
    names = []
    for argument in arguments:
        extensions = (
            initial_extensions
            if argument == 'all'
            else ('cogs.' + argument,)
        )
        for extension in extensions:
            if extension not in names:
                names.append(extension)
    return names


class SystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = bot.settings

    @commands.group(name='system')
    async def botsystem(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Error: missing option')

    @botsystem.command(name='close')
    @commands.is_owner()
    async def botsystem_close(self, ctx):
        await self.bot.get_channel(self.settings.LOG_CHANNEL).send('Bot System Will Be Shutdown...')
        await asyncio.sleep(3)
        await self.bot.close()

    @commands.group(name='cog')
    async def cogs(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Error: missing option')

    @cogs.group(name='reload')
    @commands.is_owner()
    async def cogs_reload(self, ctx, *args, **kwargs):
        if len(args) == 0:
            await ctx.send('Error: missing cog name opetand')
            return

        for extension in _extension_names(
            args,
            self.settings.INITIAL_EXTENSIONS,
        ):
            await self.bot.reload_extension(extension)
            await ctx.send('Success: ' + extension + ' is Reloaded.')

    @cogs_reload.error
    async def cogs_reload_error(self, ctx, error):
        await ctx.send('Error: ' + str(error))

    @cogs.group(name='load')
    @commands.is_owner()
    async def cogs_load(self, ctx, *args, **kwargs):
        if len(args) == 0:
            await ctx.send('Error: missing cog name opetand')
            return

        for extension in _extension_names(
            args,
            self.settings.INITIAL_EXTENSIONS,
        ):
            await self.bot.load_extension(extension)
            await ctx.send('Success: ' + extension + ' is Loaded.')
    
    @cogs_load.error
    async def cogs_load_error(self, ctx, error):
        await ctx.send('Error: ' + str(error))

    @cogs.group(name='unload')
    @commands.is_owner()
    async def cogs_unload(self, ctx, *args, **kwargs):
        if len(args) == 0:
            await ctx.send('Error: missing cog name opetand')
            return

        force_option = '-f' in args
        targets = tuple(argument for argument in args if argument != '-f')
        if not targets:
            await ctx.send('Error: missing cog name opetand')
            return
        if 'all' in targets and not force_option:
            await ctx.send("Error: can't unload. (force unload : -f)")
            return
        if 'systemcog' in targets and not force_option:
            await ctx.send("Error: systemcog can't unload. (force unload : -f)")
            return

        for extension in _extension_names(
            targets,
            self.settings.INITIAL_EXTENSIONS,
        ):
            await self.bot.unload_extension(extension)
            await ctx.send('Success: ' + extension + ' is Unloaded.')
    
    @cogs_unload.error
    async def cogs_unload_error(self, ctx, error):
        await ctx.send('Error: ' + str(error))

    @commands.command(enabled=False)
    async def send_log(self, ctx, *args, **kwargs):
        await self.bot.get_channel(self.settings.LOG_CHANNEL).send('``' + '\n'.join(args) + '``')
    
    @commands.command(enabled=False)
    async def send_error_log(self, ctx, error, *args, **kwargs):
        log_channel = self.bot.get_channel(self.settings.LOG_CHANNEL)
        error_log = format_exception_traceback(error)

        # Persist the complete traceback before attempting Discord I/O. This
        # ensures a failed notification never hides the original error.
        self.bot.logger.error(error_log)

        await ctx.reply('Error: Check ' + log_channel.mention)

        field_number = 1
        for field_batch in split_traceback_for_embeds(error_log):
            embed = Embed()
            for field_value in field_batch:
                embed.add_field(
                    name=f'Traceback {field_number}',
                    value=field_value,
                    inline=False,
                )
                field_number += 1
            await log_channel.send(embed=embed)


    @commands.command(enabled=False)
    async def send_video_output_log(self, ctx, info, url):
        await self.bot.get_channel(self.settings.VIDEO_OUTPUT_CHANNEL).send('**Download Success : **' + '%(title)s' % info + '\n' + url)

    @commands.command(enabled=False)
    async def send_highlight_output_log(self, ctx, file, embed):
        await self.bot.get_channel(self.settings.HIGHLIGHT_OUTPUT_CHANNEL).send(file=file, embed=embed)

async def setup(bot):
    await bot.add_cog(SystemCog(bot))

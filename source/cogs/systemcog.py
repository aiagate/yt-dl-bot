#! ./.venv/bin/python

# ---standard library---
import asyncio
import traceback

# ---third party library---
from discord import Embed
from discord.ext import commands

# ---local library---
import property


def _extension_names(arguments):
    """Expand ``all`` and remove duplicate extension names."""
    names = []
    for argument in arguments:
        extensions = (
            property.INITIAL_EXTENSIONS
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

    @commands.group(name='system')
    async def botsystem(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Error: missing option')

    @botsystem.command(name='close')
    @commands.is_owner()
    async def botsystem_close(self, ctx):
        await self.bot.get_channel(property.LOG_CHANNEL).send('Bot System Will Be Shutdown...')
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

        for extension in _extension_names(args):
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

        for extension in _extension_names(args):
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

        for extension in _extension_names(targets):
            await self.bot.unload_extension(extension)
            await ctx.send('Success: ' + extension + ' is Unloaded.')
    
    @cogs_unload.error
    async def cogs_unload_error(self, ctx, error):
        await ctx.send('Error: ' + str(error))

    @commands.command(enabled=False)
    async def send_log(self, ctx, *args, **kwargs):
        await self.bot.get_channel(property.LOG_CHANNEL).send('``' + '\n'.join(args) + '``')
    
    @commands.command(enabled=False)
    async def send_error_log(self, ctx, error, *args, **kwargs):
        log_channel = self.bot.get_channel(property.LOG_CHANNEL)
        await ctx.reply('Error: Check ' + log_channel.mention)

        error_log = str(traceback.format_exc())

        embed = Embed(title='', description='') #, color=0xff0000)
        num = 1
        while len(error_log) > 1024:
            embed.add_field(name=str(num), value=error_log[:1024], inline=False)
            error_log = error_log[1024:]
            num += 1
        embed.add_field(name=str(num), value=error_log, inline=False)
        
        await self.bot.get_channel(property.LOG_CHANNEL).send(embed = embed)

        # self.logger.exception(traceback.format_exc())
        # self.bot.logger.exception(traceback.format_exc())
        for line in error_log.split('\n'):
            self.bot.logger.error(line)


        # await self.bot.get_channel(property.LOG_CHANNEL).send('```' + traceback.format_exc() + '```')

    @commands.command(enabled=False)
    async def send_video_output_log(self, ctx, info, url):
        await self.bot.get_channel(property.VIDEO_OUTPUT_CHANNEL).send('**Download Success : **' + '%(title)s' % info + '\n' + url)

    @commands.command(enabled=False)
    async def send_highlight_output_log(self, ctx, file, embed):
        await self.bot.get_channel(property.HIGHLIGHT_OUTPUT_CHANNEL).send(file=file, embed=embed)

async def setup(bot):
    await bot.add_cog(SystemCog(bot))

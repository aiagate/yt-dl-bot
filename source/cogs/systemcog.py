#! ./.venv/bin/python

# ---standard library---
import asyncio
import traceback

# ---third party library---
from discord import Embed
from discord.ext import commands

# ---local library---
import property

class SystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='system')
    async def botsystem(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Error: missing option')

    @botsystem.command(name='close')
    async def botsystem_close(self, ctx):
        await self.bot.get_channel(property.LOG_CHANNEL).send('Bot System Will Be Shutdown...')
        await asyncio.sleep(3)
        await self.bot.close()

    @commands.group(name='cog')
    async def cogs(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Error: missing option')

    @cogs.group(name='reload')
    async def cogs_reload(self, ctx, *args, **kwargs):
        if len(args) == 0:
            await ctx.send('Error: missing cog name opetand')
            return

        for cog in args:
            if cog == 'all':
                for cog in property.INITIAL_EXTENSIONS:
                    await self.bot.reload_extension(cog)
                    await ctx.send('Success: ' + cog + ' is Reloaded.')
            else:
                await self.bot.reload_extension('cogs.' + cog)
                await ctx.send('Success: cog.' + cog + ' is Reloaded.')

    @cogs_reload.error
    async def cogs_reload_error(self, ctx, error):
        await ctx.send('Error: ' + str(error))

    @cogs.group(name='load')
    async def cogs_load(self, ctx, *args, **kwargs):
        if len(args) == 0:
            await ctx.send('Error: missing cog name opetand')
            return

        for cog in args:
            if cog == 'all':
                for cog in property.INITIAL_EXTENSIONS:
                    self.bot.load_extension(cog)
                    await ctx.send('Success: ' + cog + ' is Loaded.')
            else:
                self.bot.load_extension('cogs.' + cog)
                await ctx.send('Success: cog.' + cog + ' is Loaded.')
    
    @cogs_load.error
    async def cogs_load_error(self, ctx, error):
        await ctx.send('Error: ' + str(error))

    @cogs_load.command(name='all')
    async def cogs_load_all(self, ctx):
        pass
    
    @cogs_load_all.error
    async def cogs_load_all_error(self, ctx, error):
        await ctx.send('Error: ' + str(error))

    @cogs.group(name='unload')
    async def cogs_unload(self, ctx, *args, **kwargs):
        force_option = False

        if len(args) == 0:
            await ctx.send('Error: missing cog name opetand')
            return

        for cog in args:
            if cog == '-f':
                force_option = True
        
        for cog in args:
            if cog == 'all':
                if force_option == False:
                        await ctx.send("Error: can't unload. (force unload : -f)")
                        return
                for cog in property.INITIAL_EXTENSIONS:
                    self.bot.unload_extension(cog)
                    await ctx.send('Success: ' + cog + ' is Unloaded.')

            if cog == 'systemcog' and force_option == True:
                pass
            elif cog == 'systemcog' and force_option == False:
                await ctx.send("Error: systemcog can't unload. (force unload : -f)")
                return

            self.bot.unload_extension('cogs.' + cog)
            await ctx.send('Success: cog.' + cog + ' is Unloaded.')
    
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

    @commands.command(enabled=False)
    async def send_search_output_log(self, ctx, embed):
        await self.bot.get_channel(property.SEARCH_OUTPUT_CHANNEL).send(embed=embed)


def setup(bot):
    return bot.add_cog(SystemCog(bot))

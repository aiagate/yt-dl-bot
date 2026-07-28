#! .venv/bin/python

# ---standard library---
import logging
from logging import DEBUG, INFO, Logger, getLogger
from pathlib import Path

# ---third party library---
import discord
from discord.ext import commands

# ---local library---
from application_services import ApplicationServices
from setting import Settings


class MyBot(commands.Bot):

    def __init__(self, command_prefix, settings, services=None):
        # loggerを作成
        self.logger = getLogger(__name__)
        self.settings = settings
        self.services = (
            services
            if services is not None
            else ApplicationServices.from_settings(settings)
        )

        # スーパークラスのコンストラクタに値を渡して実行。
        super().__init__(intents=discord.Intents.all(),command_prefix=command_prefix)


    async def setup_hook(self):
        # Cogをpropartyのリストからロード
        for cog in self.settings.INITIAL_EXTENSIONS:
            try:
                await self.load_extension(cog)
                self.logger.info(f'Success: Cog loaded ({cog})')
            except Exception:
                self.logger.exception('Failed to load Cog: %s', cog)
                raise
                # traceback.print_exc()

    async def on_ready(self):
        self.logger.info('----------------')
        self.logger.info(self.user.name)
        self.logger.info(self.user.id)
        self.logger.info('----------------')

def main(settings=None):
    settings = settings or Settings()
    logging.basicConfig(
        level=INFO,
        format='[ %(levelname)-8s] %(asctime)s | %(name)-16s %(funcName)-16s| %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    log_path = Path(settings.LOG_PATH)
    log_path.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(filename=log_path / 'discord_bot_main.log', encoding='utf-8')
    fh.setLevel=INFO
    fh.setFormatter(logging.Formatter('[ %(levelname)-8s] %(asctime)s | %(name)-16s %(funcName)-24s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

    dlogger = getLogger('discord')
    dlogger.addHandler(fh)
    logger = getLogger(__name__)
    logger.addHandler(fh)

    services = ApplicationServices.from_settings(settings)
    bot = MyBot(
        command_prefix='!',
        settings=settings,
        services=services,
    )
    bot.run(settings.DISCORD_KEY.get_secret_value())
    logger2 = getLogger('youtubemodule')
    logger2.addHandler(fh)


if __name__ == '__main__':
    main()

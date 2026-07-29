# ---standard library---
import logging
from collections.abc import Callable
from logging import INFO, getLogger
from pathlib import Path

# ---third party library---
import discord
from discord.ext import commands

# ---local library---
from .application_container import ApplicationServices
from .setting import Settings

LOG_FORMAT = "[ %(levelname)-8s] %(asctime)s | %(name)-16s %(funcName)-24s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
FILE_LOGGERS = ("discord", __name__, "yt_dl_bot.youtube_downloader")


def build_gateway_intents() -> discord.Intents:
    """Return only the gateway intents needed by commands and message routing."""
    intents = discord.Intents.none()
    intents.guilds = True
    intents.guild_messages = True
    intents.dm_messages = True
    intents.message_content = True
    return intents


def configure_logging(log_path: Path) -> logging.FileHandler:
    """Configure application file logging once and return its handler."""
    logging.basicConfig(
        level=INFO,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )

    log_path = Path(log_path)
    log_path.mkdir(parents=True, exist_ok=True)
    filename = (log_path / "discord_bot_main.log").resolve()
    loggers = [getLogger(name) for name in FILE_LOGGERS]

    matching_handlers = []
    for logger in loggers:
        for handler in logger.handlers:
            if (
                isinstance(handler, logging.FileHandler)
                and Path(handler.baseFilename).resolve() == filename
                and handler not in matching_handlers
            ):
                matching_handlers.append(handler)

    if matching_handlers:
        handler = matching_handlers[0]
    else:
        handler = logging.FileHandler(
            filename=filename,
            encoding="utf-8",
        )

    handler.setLevel(INFO)
    handler.setFormatter(
        logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT),
    )

    for logger in loggers:
        logger.setLevel(INFO)
        for duplicate in tuple(logger.handlers):
            if (
                duplicate is not handler
                and isinstance(duplicate, logging.FileHandler)
                and Path(duplicate.baseFilename).resolve() == filename
            ):
                logger.removeHandler(duplicate)
        if handler not in logger.handlers:
            logger.addHandler(handler)
    return handler


class DownloadBot(commands.Bot):
    def __init__(
        self,
        command_prefix: str | Callable[..., str],
        settings: Settings,
        services: ApplicationServices | None = None,
    ) -> None:
        # loggerを作成
        self.logger = getLogger(__name__)
        self.settings = settings
        self.services = (
            services if services is not None else ApplicationServices.from_settings(settings)
        )

        # スーパークラスのコンストラクタに値を渡して実行。
        super().__init__(intents=build_gateway_intents(), command_prefix=command_prefix)

    async def setup_hook(self) -> None:
        # 設定されたリストからCogをロード
        for cog in self.settings.INITIAL_EXTENSIONS:
            try:
                await self.load_extension(cog)
                self.logger.info(f"Success: Cog loaded ({cog})")
            except Exception:
                self.logger.exception("Failed to load Cog: %s", cog)
                raise
                # traceback.print_exc()

    async def on_ready(self) -> None:
        user = self.user
        if user is None:
            self.logger.warning("Discord client is ready without an authenticated user")
            return
        self.logger.info("----------------")
        self.logger.info(user.name)
        self.logger.info(user.id)
        self.logger.info("----------------")


def main(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    configure_logging(settings.LOG_PATH)

    services = ApplicationServices.from_settings(settings)
    bot = DownloadBot(
        command_prefix="!",
        settings=settings,
        services=services,
    )
    bot.run(settings.DISCORD_KEY.get_secret_value())


if __name__ == "__main__":
    main()

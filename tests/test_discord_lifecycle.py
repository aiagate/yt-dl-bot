import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from yt_dl_bot.cogs import maincog, systemcog, twitchcog, youtubecog
from yt_dl_bot.discord_bot_main import MyBot

INITIAL_EXTENSIONS = (
    "yt_dl_bot.cogs.maincog",
    "yt_dl_bot.cogs.systemcog",
    "yt_dl_bot.cogs.youtubecog",
    "yt_dl_bot.cogs.twitchcog",
)


class BotLifecycleTest(unittest.IsolatedAsyncioTestCase):
    async def test_setup_hook_loads_initial_extensions(self):
        settings = SimpleNamespace(
            INITIAL_EXTENSIONS=INITIAL_EXTENSIONS,
        )
        bot = MyBot(
            command_prefix="!",
            settings=settings,
            services=SimpleNamespace(),
        )
        bot.load_extension = AsyncMock()
        self.addAsyncCleanup(bot.close)

        await bot.setup_hook()

        self.assertEqual(
            bot.load_extension.await_args_list,
            [unittest.mock.call(cog) for cog in INITIAL_EXTENSIONS],
        )

    async def test_ready_event_does_not_load_extensions(self):
        bot = MyBot(
            command_prefix="!",
            settings=SimpleNamespace(INITIAL_EXTENSIONS=()),
            services=SimpleNamespace(),
        )
        bot.load_extension = AsyncMock()
        bot._connection.user = unittest.mock.Mock(name="bot", id=1)
        self.addAsyncCleanup(bot.close)

        await bot.on_ready()

        bot.load_extension.assert_not_awaited()


class CogSetupTest(unittest.IsolatedAsyncioTestCase):
    async def test_each_extension_awaits_cog_registration(self):
        cases = (
            (maincog, maincog.MainCog),
            (systemcog, systemcog.SystemCog),
            (twitchcog, twitchcog.TwitchCog),
            (youtubecog, youtubecog.YoutubeCog),
        )

        for module, cog_type in cases:
            with self.subTest(module=module.__name__):
                bot = unittest.mock.Mock()
                bot.add_cog = AsyncMock()

                await module.setup(bot)

                bot.add_cog.assert_awaited_once()
                registered_cog = bot.add_cog.await_args.args[0]
                self.assertIsInstance(registered_cog, cog_type)
                self.assertIs(registered_cog.bot, bot)
                self.assertIs(registered_cog.settings, bot.settings)


if __name__ == "__main__":
    unittest.main()

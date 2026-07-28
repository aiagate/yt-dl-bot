import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


SOURCE_PATH = Path(__file__).resolve().parents[1] / 'source'
sys.path.insert(0, str(SOURCE_PATH))

REQUIRED_ENVIRONMENT = {
    'DISCORD_KEY': 'discord-token',
    'LOG_CHANNEL': '1',
    'VIDEO_OUTPUT_CHANNEL': '2',
    'HIGHLIGHT_OUTPUT_CHANNEL': '3',
    'DOWNLOAD_CHANNEL': '4',
    'HIGHLIGHT_CHANNEL': '5',
}

with patch.dict(os.environ, REQUIRED_ENVIRONMENT):
    import property
    from cogs import maincog, systemcog, twitchcog, youtubecog
    from discord_bot_main import MyBot


class BotLifecycleTest(unittest.IsolatedAsyncioTestCase):
    async def test_setup_hook_loads_initial_extensions(self):
        bot = MyBot(command_prefix='!')
        bot.load_extension = AsyncMock()
        self.addAsyncCleanup(bot.close)

        await bot.setup_hook()

        self.assertEqual(
            bot.load_extension.await_args_list,
            [unittest.mock.call(cog) for cog in property.INITIAL_EXTENSIONS],
        )

    async def test_ready_event_does_not_load_extensions(self):
        bot = MyBot(command_prefix='!')
        bot.load_extension = AsyncMock()
        bot._connection.user = unittest.mock.Mock(name='bot', id=1)
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


if __name__ == '__main__':
    unittest.main()

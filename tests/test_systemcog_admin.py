import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, patch

from discord.ext import commands


SOURCE_PATH = Path(__file__).resolve().parents[1] / 'source'
sys.path.insert(0, str(SOURCE_PATH))

from cogs.systemcog import SystemCog


INITIAL_EXTENSIONS = (
    'cogs.maincog',
    'cogs.systemcog',
    'cogs.youtubecog',
    'cogs.twitchcog',
)


class OwnerChecksTest(unittest.IsolatedAsyncioTestCase):
    async def test_admin_commands_require_bot_owner(self):
        admin_commands = (
            SystemCog.botsystem_close,
            SystemCog.cogs_load,
            SystemCog.cogs_reload,
            SystemCog.cogs_unload,
        )

        for command in admin_commands:
            with self.subTest(command=command.qualified_name):
                bot = Mock()
                bot.is_owner = AsyncMock(return_value=False)
                ctx = Mock(bot=bot, author=Mock())

                self.assertTrue(command.checks)
                with self.assertRaises(commands.NotOwner):
                    await command.checks[0](ctx)
                bot.is_owner.assert_awaited_once_with(ctx.author)

    async def test_admin_commands_allow_bot_owner(self):
        bot = Mock()
        bot.is_owner = AsyncMock(return_value=True)
        ctx = Mock(bot=bot, author=Mock())

        for command in (
            SystemCog.botsystem_close,
            SystemCog.cogs_load,
            SystemCog.cogs_reload,
            SystemCog.cogs_unload,
        ):
            with self.subTest(command=command.qualified_name):
                self.assertTrue(await command.checks[0](ctx))


class ExtensionCommandsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = Mock()
        self.bot.load_extension = AsyncMock()
        self.bot.reload_extension = AsyncMock()
        self.bot.unload_extension = AsyncMock()
        self.bot.settings = SimpleNamespace(
            INITIAL_EXTENSIONS=INITIAL_EXTENSIONS,
            LOG_CHANNEL=1,
            VIDEO_OUTPUT_CHANNEL=2,
            HIGHLIGHT_OUTPUT_CHANNEL=3,
        )
        self.cog = SystemCog(self.bot)
        self.ctx = Mock()
        self.ctx.send = AsyncMock()

    async def test_close_awaits_shutdown(self):
        channel = Mock()
        channel.send = AsyncMock()
        self.bot.get_channel.return_value = channel
        self.bot.close = AsyncMock()

        with patch('cogs.systemcog.asyncio.sleep', new=AsyncMock()) as sleep:
            await SystemCog.botsystem_close.callback(self.cog, self.ctx)

        channel.send.assert_awaited_once()
        sleep.assert_awaited_once_with(3)
        self.bot.close.assert_awaited_once_with()

    async def test_load_all_awaits_each_initial_extension_once(self):
        await SystemCog.cogs_load.callback(self.cog, self.ctx, 'all')

        self.bot.load_extension.assert_has_awaits(
            [call(extension) for extension in INITIAL_EXTENSIONS],
        )
        self.assertEqual(
            self.bot.load_extension.await_count,
            len(INITIAL_EXTENSIONS),
        )

    async def test_load_awaits_each_unique_extension(self):
        await SystemCog.cogs_load.callback(
            self.cog, self.ctx, 'maincog', 'maincog',
        )

        self.bot.load_extension.assert_has_awaits(
            [call('cogs.maincog')],
        )

    async def test_reload_all_awaits_each_initial_extension_once(self):
        await SystemCog.cogs_reload.callback(
            self.cog, self.ctx, 'all', 'maincog',
        )

        self.bot.reload_extension.assert_has_awaits(
            [call(extension) for extension in INITIAL_EXTENSIONS],
        )
        self.assertEqual(
            self.bot.reload_extension.await_count,
            len(INITIAL_EXTENSIONS),
        )

    async def test_unload_all_force_awaits_each_extension_once(self):
        await SystemCog.cogs_unload.callback(
            self.cog, self.ctx, 'all', '-f',
        )

        self.bot.unload_extension.assert_has_awaits(
            [call(extension) for extension in INITIAL_EXTENSIONS],
        )
        self.assertEqual(
            self.bot.unload_extension.await_count,
            len(INITIAL_EXTENSIONS),
        )

    async def test_unload_all_without_force_is_rejected(self):
        await SystemCog.cogs_unload.callback(self.cog, self.ctx, 'all')

        self.bot.unload_extension.assert_not_awaited()
        self.ctx.send.assert_awaited_once_with(
            "Error: can't unload. (force unload : -f)",
        )

    async def test_unload_system_cog_without_force_is_rejected(self):
        await SystemCog.cogs_unload.callback(
            self.cog, self.ctx, 'systemcog',
        )

        self.bot.unload_extension.assert_not_awaited()
        self.ctx.send.assert_awaited_once_with(
            "Error: systemcog can't unload. (force unload : -f)",
        )


if __name__ == '__main__':
    unittest.main()

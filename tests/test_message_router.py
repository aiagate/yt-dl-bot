import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock



from yt_dl_bot.cogs.maincog import MainCog
from yt_dl_bot.message_router import MessageAction, MessageRoute, MessageRouter


class MessageRouterTest(unittest.TestCase):
    def setUp(self):
        self.router = MessageRouter(
            command_prefix='!',
            download_channel=10,
            highlight_channel=20,
        )

    def route(self, content, channel=10, author_is_bot=False):
        return self.router.route(
            author_is_bot=author_is_bot,
            content=content,
            channel_id=channel,
        )

    def test_ignores_bot_messages(self):
        self.assertEqual(
            self.route('!youtube download url', author_is_bot=True),
            MessageRoute(MessageAction.IGNORE),
        )

    def test_only_leading_prefix_is_a_command(self):
        self.assertEqual(
            self.route('!youtube download url'),
            MessageRoute(MessageAction.COMMAND),
        )
        self.assertEqual(
            self.route('ordinary ! message'),
            MessageRoute(MessageAction.IGNORE),
        )

    def test_routes_youtube_by_channel(self):
        url = 'https://youtu.be/dQw4w9WgXcQ'

        self.assertEqual(
            self.route(url, channel=10),
            MessageRoute(MessageAction.YOUTUBE_DOWNLOAD, url),
        )
        self.assertEqual(
            self.route(url, channel=20),
            MessageRoute(MessageAction.YOUTUBE_HIGHLIGHT, url),
        )

    def test_routes_twitch_only_to_download_channel(self):
        url = 'https://www.twitch.tv/channel'

        self.assertEqual(
            self.route(url, channel=10),
            MessageRoute(MessageAction.TWITCH_DOWNLOAD, url),
        )
        self.assertEqual(
            self.route(url, channel=20),
            MessageRoute(MessageAction.IGNORE),
        )

    def test_exclamation_mark_inside_url_is_not_a_command(self):
        url = 'https://youtu.be/dQw4w9WgXcQ?note=hello!world'

        self.assertEqual(
            self.route(url),
            MessageRoute(MessageAction.YOUTUBE_DOWNLOAD, url),
        )

    def test_rejects_extra_text_and_unsupported_channels(self):
        url = 'https://youtu.be/dQw4w9WgXcQ'

        self.assertEqual(
            self.route(f'please download {url}'),
            MessageRoute(MessageAction.IGNORE),
        )
        self.assertEqual(
            self.route(url, channel=99),
            MessageRoute(MessageAction.IGNORE),
        )

    def test_supports_multiple_formal_prefixes(self):
        router = MessageRouter(
            command_prefix=('!', '?'),
            download_channel=10,
            highlight_channel=20,
        )

        self.assertEqual(
            router.route(
                author_is_bot=False,
                content='?youtube download url',
                channel_id=10,
            ).action,
            MessageAction.COMMAND,
        )


class MainCogRoutingTest(unittest.IsolatedAsyncioTestCase):
    def make_bot(self):
        bot = Mock()
        bot.command_prefix = '!'
        bot.settings = SimpleNamespace(
            DOWNLOAD_CHANNEL=10,
            HIGHLIGHT_CHANNEL=20,
        )
        bot.logger = Mock()
        bot.get_context = AsyncMock()
        bot.process_commands = AsyncMock()
        return bot

    async def test_automatic_route_invokes_without_mutating_message(self):
        bot = self.make_bot()
        command = Mock(name='youtube download')
        bot.get_command.return_value = command
        ctx = Mock()
        ctx.invoke = AsyncMock()
        bot.get_context.return_value = ctx
        message = SimpleNamespace(
            author=SimpleNamespace(bot=False),
            channel=SimpleNamespace(id=10),
            content='https://youtu.be/dQw4w9WgXcQ?note=hello!world',
        )
        original_content = message.content
        cog = MainCog(bot)

        await cog.on_message(message)

        self.assertEqual(message.content, original_content)
        bot.get_command.assert_called_once_with('youtube download')
        ctx.invoke.assert_awaited_once_with(command, original_content)
        bot.process_commands.assert_not_awaited()

    async def test_normal_command_is_left_to_bot_default_handler(self):
        bot = self.make_bot()
        message = SimpleNamespace(
            author=SimpleNamespace(bot=False),
            channel=SimpleNamespace(id=10),
            content='!youtube download https://youtu.be/dQw4w9WgXcQ',
        )

        await MainCog(bot).on_message(message)

        bot.get_context.assert_not_awaited()
        bot.process_commands.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()

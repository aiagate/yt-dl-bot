import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch


SOURCE_PATH = Path(__file__).resolve().parents[1] / 'source'
sys.path.insert(0, str(SOURCE_PATH))

from application_services import (
    DownloadResult,
    HighlightResult,
    TwitchDownloadService,
    TwitchStreamOffline,
    VideoDownloadService,
    YoutubeHighlightService,
    split_highlight_text,
)
from cogs.twitchcog import TwitchCog
from cogs.youtubecog import YoutubeCog


class VideoDownloadServiceTest(unittest.TestCase):
    def test_success_flow_delegates_and_returns_domain_result(self):
        downloader = Mock()
        downloader.data_check.return_value = 'ready'
        downloader.download_video.return_value = {'id': 'video'}
        service = VideoDownloadService(downloader)

        self.assertEqual(service.check('https://example.test'), 'ready')
        self.assertEqual(
            service.download('https://example.test'),
            DownloadResult(
                url='https://example.test',
                info={'id': 'video'},
            ),
        )
        downloader.data_check.assert_called_once_with(
            url='https://example.test',
            ydl_ops={},
        )
        downloader.download_video.assert_called_once_with(
            url='https://example.test',
        )

    def test_download_failure_is_propagated(self):
        downloader = Mock()
        failure = RuntimeError('download failed')
        downloader.download_video.side_effect = failure

        with self.assertRaises(RuntimeError) as raised:
            VideoDownloadService(downloader).download(
                'https://example.test',
            )

        self.assertIs(raised.exception, failure)


class TwitchDownloadServiceTest(unittest.TestCase):
    def test_offline_error_is_translated(self):
        downloader = Mock()
        error = RuntimeError('extract failed')
        error.exc_info = (
            None,
            RuntimeError('The channel is not currently live'),
            None,
        )
        downloader.data_check.side_effect = error

        with self.assertRaises(TwitchStreamOffline):
            TwitchDownloadService(downloader).check(
                'https://www.twitch.tv/channel',
            )

    def test_other_error_is_propagated(self):
        downloader = Mock()
        error = RuntimeError('network failed')
        downloader.data_check.side_effect = error

        with self.assertRaises(RuntimeError) as raised:
            TwitchDownloadService(downloader).check(
                'https://www.twitch.tv/channel',
            )

        self.assertIs(raised.exception, error)


class HighlightServiceTest(unittest.TestCase):
    def test_create_returns_discord_independent_highlight_result(self):
        youtube = Mock()
        youtube.get_videoid.return_value = 'video-id'
        youtube.get_info.return_value = {
            'title': 'Title',
            'fulltitle': 'Full title',
            'channel': 'Channel',
            'thumbnail': 'https://example.test/thumb.jpg',
        }
        chat = Mock()
        chat.image_path = '/tmp/graph.png'
        chat.get_highlight.return_value = [
            [30, 'https://youtu.be/video-id?t=30s'],
            [90, 'https://youtu.be/video-id?t=90s'],
        ]
        service = YoutubeHighlightService(
            settings=SimpleNamespace(GRAPH_SAVE_PATH='/graphs/'),
            youtube=youtube,
            chat_factory=Mock(return_value=chat),
        )

        result = service.create('https://youtu.be/video-id')

        self.assertEqual(result.title, 'Full title')
        self.assertEqual(result.channel_name, 'Channel')
        self.assertEqual(result.graph_image, '/tmp/graph.png')
        self.assertEqual(
            result.highlight_fields,
            (
                '0:00:30\thttps://youtu.be/video-id?t=30s\n'
                '0:01:30\thttps://youtu.be/video-id?t=90s\n',
            ),
        )

    def test_archive_graph_uses_injected_file_operations(self):
        mkdir = Mock()
        move = Mock()
        service = YoutubeHighlightService(
            settings=SimpleNamespace(GRAPH_SAVE_PATH='/graphs/'),
            youtube=Mock(),
            path_exists=Mock(return_value=False),
            make_directory=mkdir,
            move=move,
        )

        service.archive_graph('/tmp/graph.png')

        mkdir.assert_called_once_with('/graphs/')
        move.assert_called_once_with('/tmp/graph.png', '/graphs/')

    def test_empty_highlights_get_a_placeholder(self):
        self.assertEqual(
            split_highlight_text([]),
            ('does not get highlight',),
        )

    def test_highlight_text_is_split_before_field_limit(self):
        highlights = [
            (index, f'https://example.test/{index}/' + ('x' * 30))
            for index in range(10)
        ]

        fields = split_highlight_text(highlights, max_length=120)

        self.assertGreater(len(fields), 1)
        self.assertTrue(all(len(field) < 120 for field in fields))


class CogDelegationTest(unittest.IsolatedAsyncioTestCase):
    def make_bot(self):
        bot = Mock()
        bot.settings = SimpleNamespace()
        bot.services = SimpleNamespace(
            youtube_download=Mock(),
            youtube_highlight=Mock(),
            twitch_download=Mock(),
        )
        bot.logger = Mock()
        bot.get_command.side_effect = lambda name: name

        async def run_in_executor(executor, function):
            return function()

        bot.loop.run_in_executor = AsyncMock(side_effect=run_in_executor)
        return bot

    async def test_youtube_cog_only_coordinates_download_responses(self):
        bot = self.make_bot()
        bot.services.youtube_download.check.return_value = 'ready'
        bot.services.youtube_download.download.return_value = DownloadResult(
            url='https://youtu.be/video',
            info={'id': 'video'},
        )
        ctx = Mock()
        ctx.reply = AsyncMock()
        ctx.invoke = AsyncMock()
        cog = YoutubeCog(bot)

        await YoutubeCog.download_video.callback(
            cog,
            ctx,
            'https://youtu.be/video',
        )

        bot.services.youtube_download.check.assert_called_once_with(
            'https://youtu.be/video',
        )
        bot.services.youtube_download.download.assert_called_once_with(
            'https://youtu.be/video',
        )
        ctx.reply.assert_awaited_once_with('ready')
        ctx.invoke.assert_awaited_once_with(
            'send_video_output_log',
            info={'id': 'video'},
            url='https://youtu.be/video',
        )

    async def test_twitch_cog_maps_offline_result_to_reply(self):
        bot = self.make_bot()
        bot.services.twitch_download.check.side_effect = TwitchStreamOffline
        ctx = Mock()
        ctx.reply = AsyncMock()
        ctx.invoke = AsyncMock()
        cog = TwitchCog(bot)

        await TwitchCog.download_video.callback(
            cog,
            ctx,
            'https://www.twitch.tv/channel',
        )

        ctx.reply.assert_awaited_once_with(
            'このチャンネルでライブは始まっていません。',
        )
        bot.services.twitch_download.download.assert_not_called()
        ctx.invoke.assert_not_awaited()

    async def test_youtube_cog_converts_highlight_result_to_discord_types(self):
        bot = self.make_bot()
        result = HighlightResult(
            title='Title',
            channel_name='Channel',
            thumbnail_url='https://example.test/thumb.jpg',
            graph_image='/tmp/graph.png',
            highlight_fields=('field one', 'field two'),
        )
        bot.services.youtube_highlight.create.return_value = result
        ctx = Mock()
        ctx.reply = AsyncMock()
        ctx.invoke = AsyncMock()
        cog = YoutubeCog(bot)
        embed = Mock()

        with (
            patch('cogs.youtubecog.File', return_value='discord-file'),
            patch('cogs.youtubecog.Embed', return_value=embed),
        ):
            await YoutubeCog.get_highlight.callback(
                cog,
                ctx,
                'https://youtu.be/video',
            )

        bot.services.youtube_highlight.create.assert_called_once_with(
            'https://youtu.be/video',
        )
        bot.services.youtube_highlight.archive_graph.assert_called_once_with(
            '/tmp/graph.png',
        )
        self.assertEqual(
            embed.add_field.call_args_list,
            [
                unittest.mock.call(name='highlight', value='field one'),
                unittest.mock.call(name='highlight', value='field two'),
            ],
        )
        ctx.invoke.assert_awaited_once_with(
            'send_highlight_output_log',
            'discord-file',
            embed,
        )


if __name__ == '__main__':
    unittest.main()

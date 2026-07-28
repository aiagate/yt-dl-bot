import asyncio
import sys
import traceback
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import yt_dlp


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
from application_errors import (
    ArtifactStorageError,
    HighlightCreationError,
    VideoCheckError,
    VideoDownloadError,
)
from cogs.twitchcog import TwitchCog
from cogs.youtubecog import YoutubeCog
from cancellation import CancellationToken
from artifact_discovery import DownloadedArtifacts
from download_engine import DownloadOutcome


class VideoDownloadServiceTest(unittest.TestCase):
    def test_success_flow_delegates_and_returns_domain_result(self):
        downloader = Mock()
        downloader.data_check.return_value = 'ready'
        downloader.download_video.return_value = DownloadOutcome(
            video_id='video',
            title='Example video',
            source_url='https://example.test',
            artifacts=DownloadedArtifacts(
                video=Path('/archive/video.mkv'),
                metadata=(Path('/archive/metadata/video.info.json'),),
                thumbnails=(Path('/archive/thumbnail/video.webp'),),
            ),
        )
        service = VideoDownloadService(downloader)

        self.assertEqual(service.check('https://example.test'), 'ready')
        self.assertEqual(
            service.download('https://example.test'),
            DownloadResult(
                video_id='video',
                title='Example video',
                source_url='https://example.test',
                video_file=Path('/archive/video.mkv'),
                metadata_files=(
                    Path('/archive/metadata/video.info.json'),
                ),
                thumbnail_files=(
                    Path('/archive/thumbnail/video.webp'),
                ),
            ),
        )
        downloader.data_check.assert_called_once_with(
            url='https://example.test',
        )
        downloader.download_video.assert_called_once_with(
            url='https://example.test',
        )

    def test_download_failure_is_propagated(self):
        downloader = Mock()
        failure = yt_dlp.utils.DownloadError('download failed')
        downloader.download_video.side_effect = failure

        with self.assertRaises(VideoDownloadError) as raised:
            VideoDownloadService(downloader).download(
                'https://example.test',
            )

        self.assertIs(raised.exception.original_error, failure)
        self.assertIs(raised.exception.__cause__, failure)

    def test_cancellable_download_uses_explicit_adapter_boundary(self):
        downloader = Mock()
        downloader.download_video_cancellable.return_value = DownloadOutcome(
            video_id='video',
            title='Example video',
            source_url='https://example.test',
            artifacts=DownloadedArtifacts(
                video=Path('/archive/video.mkv'),
                metadata=(),
                thumbnails=(),
            ),
        )
        token = CancellationToken()

        result = VideoDownloadService(downloader).download(
            'https://example.test',
            cancellation_token=token,
        )

        self.assertEqual(result.video_id, 'video')
        self.assertEqual(result.title, 'Example video')
        downloader.download_video.assert_not_called()
        downloader.download_video_cancellable.assert_called_once_with(
            url='https://example.test',
            cancellation_token=token,
        )

    def test_typed_error_preserves_original_traceback(self):
        downloader = Mock()

        def fail_download(*, url):
            raise OSError(f'adapter failure for {url}')

        downloader.download_video.side_effect = fail_download

        with self.assertRaises(VideoDownloadError) as raised:
            VideoDownloadService(downloader).download(
                'https://example.test',
            )

        cause = raised.exception.__cause__
        self.assertIsInstance(cause, OSError)
        self.assertIsNotNone(cause.__traceback__)
        formatted = ''.join(traceback.format_exception(raised.exception))
        self.assertIn('fail_download', formatted)
        self.assertIn(
            'The above exception was the direct cause',
            formatted,
        )

    def test_unexpected_download_failure_is_not_translated(self):
        downloader = Mock()
        failure = RuntimeError('programming error')
        downloader.download_video.side_effect = failure

        with self.assertRaises(RuntimeError) as raised:
            VideoDownloadService(downloader).download(
                'https://example.test',
            )

        self.assertIs(raised.exception, failure)

    def test_unexpected_check_failure_is_not_translated(self):
        downloader = Mock()
        failure = AttributeError('broken adapter implementation')
        downloader.data_check.side_effect = failure

        with self.assertRaises(AttributeError) as raised:
            VideoDownloadService(downloader).check(
                'https://example.test',
            )

        self.assertIs(raised.exception, failure)


class TwitchDownloadServiceTest(unittest.TestCase):
    def test_offline_error_is_translated(self):
        downloader = Mock()
        error = yt_dlp.utils.DownloadError('extract failed')
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

        downloader.data_check.assert_called_once_with(
            url='https://www.twitch.tv/channel',
        )

    def test_other_error_is_propagated(self):
        downloader = Mock()
        error = yt_dlp.utils.DownloadError('network failed')
        downloader.data_check.side_effect = error

        with self.assertRaises(VideoCheckError) as raised:
            TwitchDownloadService(downloader).check(
                'https://www.twitch.tv/channel',
            )

        self.assertIs(raised.exception.original_error, error)
        self.assertIs(raised.exception.__cause__, error)

    def test_unexpected_error_is_not_translated(self):
        downloader = Mock()
        error = TypeError('broken adapter implementation')
        downloader.data_check.side_effect = error

        with self.assertRaises(TypeError) as raised:
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
        self.assertEqual(result.graph_image, Path('/tmp/graph.png'))
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

        mkdir.assert_called_once_with(
            Path('/graphs'),
            parents=True,
            exist_ok=True,
        )
        move.assert_called_once_with(
            Path('/tmp/graph.png'),
            Path('/graphs'),
        )

    def test_highlight_external_failure_is_typed(self):
        youtube = Mock()
        failure = yt_dlp.utils.DownloadError('yt-dlp failed')
        youtube.get_videoid.side_effect = failure
        service = YoutubeHighlightService(
            settings=SimpleNamespace(GRAPH_SAVE_PATH='/graphs/'),
            youtube=youtube,
        )

        with self.assertRaises(HighlightCreationError) as raised:
            service.create('https://youtu.be/video')

        self.assertIs(raised.exception.__cause__, failure)

    def test_unexpected_highlight_failure_is_not_translated(self):
        youtube = Mock()
        failure = AttributeError('broken highlight implementation')
        youtube.get_videoid.side_effect = failure
        service = YoutubeHighlightService(
            settings=SimpleNamespace(GRAPH_SAVE_PATH='/graphs/'),
            youtube=youtube,
        )

        with self.assertRaises(AttributeError) as raised:
            service.create('https://youtu.be/video')

        self.assertIs(raised.exception, failure)

    def test_filesystem_failure_is_typed(self):
        failure = OSError('disk full')
        service = YoutubeHighlightService(
            settings=SimpleNamespace(GRAPH_SAVE_PATH='/graphs/'),
            youtube=Mock(),
            path_exists=Mock(return_value=True),
            move=Mock(side_effect=failure),
        )

        with self.assertRaises(ArtifactStorageError) as raised:
            service.archive_graph('/tmp/graph.png')

        self.assertIs(raised.exception.__cause__, failure)

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

    def test_single_line_at_field_limit_boundaries_is_always_safe(self):
        max_length = 40
        line_prefix = '0:00:01\t'
        newline_length = 1
        cases = (
            ('max_length_minus_one', max_length - 1, max_length - 1),
            ('exactly_max_length', max_length, max_length - 1),
            ('single_line_over_limit', max_length + 10, max_length - 1),
        )

        for name, line_length, expected_length in cases:
            with self.subTest(name=name):
                url = 'x' * (
                    line_length - len(line_prefix) - newline_length
                )

                fields = split_highlight_text(
                    [(1, url)],
                    max_length=max_length,
                )

                self.assertEqual(len(fields), 1)
                self.assertEqual(len(fields[0]), expected_length)
                self.assertLess(len(fields[0]), max_length)


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

        return bot

    @staticmethod
    def to_thread_mock():
        async def run(function, *args, **kwargs):
            return function(*args, **kwargs)

        return AsyncMock(side_effect=run)

    async def test_youtube_cog_only_coordinates_download_responses(self):
        bot = self.make_bot()
        bot.services.youtube_download.check.return_value = 'ready'
        result = DownloadResult(
            video_id='video',
            title='Example video',
            source_url='https://youtu.be/video',
            video_file=Path('/archive/video.mkv'),
            metadata_files=(),
            thumbnail_files=(),
        )
        bot.services.youtube_download.download.return_value = result
        ctx = Mock()
        ctx.reply = AsyncMock()
        ctx.invoke = AsyncMock()
        cog = YoutubeCog(bot)

        to_thread = self.to_thread_mock()
        with patch('asyncio.to_thread', to_thread):
            await YoutubeCog.download_video.callback(
                cog,
                ctx,
                'https://youtu.be/video',
            )

        self.assertEqual(to_thread.await_count, 2)
        self.assertIs(
            to_thread.await_args_list[0].args[0],
            bot.services.youtube_download.check,
        )
        self.assertIs(
            to_thread.await_args_list[1].args[0],
            bot.services.youtube_download.download,
        )
        bot.services.youtube_download.check.assert_called_once_with(
            'https://youtu.be/video',
        )
        bot.services.youtube_download.download.assert_called_once_with(
            'https://youtu.be/video',
            cancellation_token=unittest.mock.ANY,
        )
        ctx.reply.assert_awaited_once_with('ready')
        ctx.invoke.assert_awaited_once_with(
            'send_video_output_log',
            result=result,
        )

    async def test_twitch_cog_maps_offline_result_to_reply(self):
        bot = self.make_bot()
        bot.services.twitch_download.check.side_effect = TwitchStreamOffline
        ctx = Mock()
        ctx.reply = AsyncMock()
        ctx.invoke = AsyncMock()
        cog = TwitchCog(bot)

        to_thread = self.to_thread_mock()
        with patch('asyncio.to_thread', to_thread):
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
            patch(
                'cogs.youtubecog.File',
                return_value='discord-file',
            ) as file_factory,
            patch('cogs.youtubecog.Embed', return_value=embed),
            patch('asyncio.to_thread', self.to_thread_mock()) as to_thread,
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
        self.assertEqual(to_thread.await_count, 3)
        self.assertIs(
            to_thread.await_args_list[0].args[0],
            bot.services.youtube_highlight.create,
        )
        self.assertIs(to_thread.await_args_list[1].args[0], file_factory)
        self.assertIs(
            to_thread.await_args_list[2].args[0],
            bot.services.youtube_highlight.archive_graph,
        )

    async def test_cancellation_stops_before_download_and_error_reply(self):
        bot = self.make_bot()
        ctx = Mock()
        ctx.reply = AsyncMock()
        ctx.invoke = AsyncMock()
        cog = YoutubeCog(bot)
        to_thread = AsyncMock(side_effect=asyncio.CancelledError)

        with (
            patch('asyncio.to_thread', to_thread),
            self.assertRaises(asyncio.CancelledError),
        ):
            await YoutubeCog.download_video.callback(
                cog,
                ctx,
                'https://youtu.be/video',
            )

        bot.services.youtube_download.download.assert_not_called()
        ctx.reply.assert_not_awaited()
        ctx.invoke.assert_not_awaited()

    async def test_command_failure_is_notified_once_by_error_handler(self):
        bot = self.make_bot()
        failure = VideoCheckError(
            'Unable to check video',
            original_error=RuntimeError('yt-dlp failed'),
        )
        bot.services.youtube_download.check.side_effect = failure
        ctx = Mock()
        ctx.reply = AsyncMock()
        ctx.invoke = AsyncMock()
        cog = YoutubeCog(bot)

        with (
            patch('asyncio.to_thread', self.to_thread_mock()),
            self.assertRaises(VideoCheckError),
        ):
            await YoutubeCog.download_video.callback(
                cog,
                ctx,
                'https://youtu.be/video',
            )

        ctx.invoke.assert_not_awaited()

        await YoutubeCog.download_video_error(
            cog,
            ctx,
            failure,
        )

        ctx.invoke.assert_awaited_once_with(
            'send_error_log',
            failure,
        )


if __name__ == '__main__':
    unittest.main()

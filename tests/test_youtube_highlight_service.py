import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import yt_dlp

from yt_dl_bot.application_errors import (
    ArtifactStorageError,
    HighlightCreationError,
)
from yt_dl_bot.highlight import Highlight
from yt_dl_bot.youtube_highlight_service import (
    YouTubeHighlightService,
)


class HighlightServiceTest(unittest.TestCase):
    def make_service(self, video_info):
        youtube = Mock()
        youtube.get_video_id.return_value = "video-id"
        youtube.get_info.return_value = video_info
        chat = Mock()
        chat.image_path = "/tmp/graph.png"
        chat.get_highlight.return_value = []
        return YouTubeHighlightService(
            settings=SimpleNamespace(GRAPH_SAVE_PATH="/graphs/"),
            youtube=youtube,
            chat_factory=Mock(return_value=chat),
        )

    def test_create_returns_discord_independent_highlight_result(self):
        youtube = Mock()
        youtube.get_video_id.return_value = "video-id"
        youtube.get_info.return_value = {
            "title": "Title",
            "fulltitle": "Full title",
            "channel": "Channel",
            "thumbnail": "https://example.test/thumb.jpg",
        }
        chat = Mock()
        chat.image_path = "/tmp/graph.png"
        chat.get_highlight.return_value = [
            Highlight(30, "https://youtu.be/video-id?t=30s"),
            Highlight(90, "https://youtu.be/video-id?t=90s"),
        ]
        service = YouTubeHighlightService(
            settings=SimpleNamespace(GRAPH_SAVE_PATH="/graphs/"),
            youtube=youtube,
            chat_factory=Mock(return_value=chat),
        )

        result = service.create("https://youtu.be/video-id")

        self.assertEqual(result.title, "Full title")
        self.assertEqual(result.channel_name, "Channel")
        self.assertEqual(result.graph_image, Path("/tmp/graph.png"))
        self.assertEqual(
            result.highlight_fields,
            (
                "0:00:30\thttps://youtu.be/video-id?t=30s\n"
                "0:01:30\thttps://youtu.be/video-id?t=90s\n",
            ),
        )

    def test_archive_graph_uses_injected_file_operations(self):
        mkdir = Mock()
        move = Mock()
        service = YouTubeHighlightService(
            settings=SimpleNamespace(GRAPH_SAVE_PATH="/graphs/"),
            youtube=Mock(),
            path_exists=Mock(return_value=False),
            make_directory=mkdir,
            move=move,
        )

        service.archive_graph("/tmp/graph.png")

        mkdir.assert_called_once_with(
            Path("/graphs"),
            parents=True,
            exist_ok=True,
        )
        move.assert_called_once_with(
            Path("/tmp/graph.png"),
            Path("/graphs"),
        )

    def test_highlight_external_failure_is_typed(self):
        youtube = Mock()
        failure = yt_dlp.utils.DownloadError("yt-dlp failed")
        youtube.get_video_id.side_effect = failure
        service = YouTubeHighlightService(
            settings=SimpleNamespace(GRAPH_SAVE_PATH="/graphs/"),
            youtube=youtube,
        )

        with self.assertRaises(HighlightCreationError) as raised:
            service.create("https://youtu.be/video")

        self.assertIs(raised.exception.__cause__, failure)

    def test_missing_fulltitle_falls_back_to_title(self):
        service = self.make_service(
            {
                "title": "Fallback title",
                "channel": "Channel",
                "thumbnail": "https://example.test/thumb.jpg",
            },
        )

        result = service.create("https://youtu.be/video-id")

        self.assertEqual(result.title, "Fallback title")

    def test_malformed_metadata_is_typed_and_preserves_cause(self):
        cases = (
            ("metadata_is_none", None, TypeError),
            (
                "title_is_missing",
                {
                    "channel": "Channel",
                    "thumbnail": "https://example.test/thumb.jpg",
                },
                KeyError,
            ),
            (
                "channel_is_missing",
                {
                    "title": "Title",
                    "thumbnail": "https://example.test/thumb.jpg",
                },
                KeyError,
            ),
            (
                "thumbnail_is_missing",
                {
                    "title": "Title",
                    "channel": "Channel",
                },
                KeyError,
            ),
            (
                "channel_is_none",
                {
                    "title": "Title",
                    "channel": None,
                    "thumbnail": "https://example.test/thumb.jpg",
                },
                ValueError,
            ),
            (
                "thumbnail_has_invalid_type",
                {
                    "title": "Title",
                    "channel": "Channel",
                    "thumbnail": 123,
                },
                ValueError,
            ),
        )

        for name, metadata, cause_type in cases:
            with self.subTest(name=name):
                service = self.make_service(metadata)

                with self.assertRaises(HighlightCreationError) as raised:
                    service.create("https://youtu.be/video-id")

                self.assertIsInstance(raised.exception.original_error, cause_type)
                self.assertIs(
                    raised.exception.__cause__,
                    raised.exception.original_error,
                )

    def test_unexpected_highlight_failure_is_not_translated(self):
        youtube = Mock()
        failure = AttributeError("broken highlight implementation")
        youtube.get_video_id.side_effect = failure
        service = YouTubeHighlightService(
            settings=SimpleNamespace(GRAPH_SAVE_PATH="/graphs/"),
            youtube=youtube,
        )

        with self.assertRaises(AttributeError) as raised:
            service.create("https://youtu.be/video")

        self.assertIs(raised.exception, failure)

    def test_filesystem_failure_is_typed(self):
        failure = OSError("disk full")
        service = YouTubeHighlightService(
            settings=SimpleNamespace(GRAPH_SAVE_PATH="/graphs/"),
            youtube=Mock(),
            path_exists=Mock(return_value=True),
            move=Mock(side_effect=failure),
        )

        with self.assertRaises(ArtifactStorageError) as raised:
            service.archive_graph("/tmp/graph.png")

        self.assertIs(raised.exception.__cause__, failure)

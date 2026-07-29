import unittest
from inspect import signature
from unittest.mock import Mock

from yt_dl_bot.application_services import (
    YouTubeHighlightService,
    YoutubeHighlightService,
)
from yt_dl_bot.chat_highlights import ChatHighlightPipeline
from yt_dl_bot.chatdatamodule import ChatDataModule
from yt_dl_bot.cogs.command_arguments import YouTubeURL, YoutubeURL
from yt_dl_bot.cogs.youtubecog import YouTubeCog, YoutubeCog
from yt_dl_bot.discord_bot_main import DownloadBot, MyBot
from yt_dl_bot.download_service import YouTubeDLFactory, YoutubeDLFactory
from yt_dl_bot.url_validation import YouTubeVideoReference, YoutubeVideoReference
from yt_dl_bot.youtube_downloader import YouTubeDownloader
from yt_dl_bot.youtubemodule import YoutubeModule
from yt_dl_bot.yt_dlp_downloader import YtDlpDownloader
from yt_dl_bot.ytdlpmodule import YtdlpModule


class NamingCompatibilityTest(unittest.TestCase):
    def test_legacy_class_names_resolve_to_canonical_classes(self):
        aliases = (
            (YoutubeHighlightService, YouTubeHighlightService),
            (ChatDataModule, ChatHighlightPipeline),
            (YoutubeURL, YouTubeURL),
            (YoutubeCog, YouTubeCog),
            (MyBot, DownloadBot),
            (YoutubeDLFactory, YouTubeDLFactory),
            (YoutubeVideoReference, YouTubeVideoReference),
            (YoutubeModule, YouTubeDownloader),
            (YtdlpModule, YtDlpDownloader),
        )

        for legacy_name, canonical_name in aliases:
            with self.subTest(canonical_name=canonical_name.__name__):
                self.assertIs(legacy_name, canonical_name)

    def test_youtube_legacy_methods_delegate_to_canonical_api(self):
        downloader = object.__new__(YouTubeDownloader)
        downloader.engine = Mock()
        downloader.engine.build_options.return_value = {"outtmpl": "target"}

        self.assertEqual(
            tuple(signature(YouTubeDownloader.build_options).parameters),
            ("self", "outpath"),
        )
        self.assertEqual(downloader.ops({"legacy": "ignored"}, "target"), {"outtmpl": "target"})
        downloader.engine.build_options.assert_called_once_with("target")

        downloader.get_video_id = Mock(return_value="video-id")
        self.assertEqual(downloader.get_videoid("https://youtu.be/video-id"), "video-id")
        downloader.get_video_id.assert_called_once_with("https://youtu.be/video-id")

    def test_yt_dlp_legacy_video_id_method_delegates_to_canonical_api(self):
        downloader = object.__new__(YtDlpDownloader)
        downloader.get_video_id = Mock(return_value="video-id")

        self.assertEqual(downloader.get_videoid("https://youtu.be/video-id"), "video-id")
        downloader.get_video_id.assert_called_once_with("https://youtu.be/video-id")

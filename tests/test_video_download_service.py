import traceback
import unittest
from pathlib import Path
from unittest.mock import Mock

import yt_dlp

from yt_dl_bot.application_errors import (
    VideoCheckError,
    VideoDownloadError,
)
from yt_dl_bot.application_results import (
    DownloadResult,
)
from yt_dl_bot.artifact_discovery import DownloadedArtifacts
from yt_dl_bot.cancellation import CancellationToken
from yt_dl_bot.download_engine import DownloadOutcome
from yt_dl_bot.video_download_service import (
    TwitchDownloadService,
    TwitchStreamOffline,
    VideoDownloadService,
)


class VideoDownloadServiceTest(unittest.TestCase):
    def test_success_flow_delegates_and_returns_domain_result(self):
        downloader = Mock()
        downloader.check_availability.return_value = "ready"
        downloader.download_video.return_value = DownloadOutcome(
            video_id="video",
            title="Example video",
            source_url="https://example.test",
            artifacts=DownloadedArtifacts(
                video=Path("/archive/video.mkv"),
                metadata=(Path("/archive/metadata/video.info.json"),),
                thumbnails=(Path("/archive/thumbnail/video.webp"),),
            ),
        )
        service = VideoDownloadService(downloader)

        self.assertEqual(service.check("https://example.test"), "ready")
        self.assertEqual(
            service.download("https://example.test"),
            DownloadResult(
                video_id="video",
                title="Example video",
                source_url="https://example.test",
                video_file=Path("/archive/video.mkv"),
                metadata_files=(Path("/archive/metadata/video.info.json"),),
                thumbnail_files=(Path("/archive/thumbnail/video.webp"),),
            ),
        )
        downloader.check_availability.assert_called_once_with(
            url="https://example.test",
        )
        downloader.download_video.assert_called_once_with(
            url="https://example.test",
        )

    def test_download_failure_is_propagated(self):
        downloader = Mock()
        failure = yt_dlp.utils.DownloadError("download failed")
        downloader.download_video.side_effect = failure

        with self.assertRaises(VideoDownloadError) as raised:
            VideoDownloadService(downloader).download(
                "https://example.test",
            )

        self.assertIs(raised.exception.original_error, failure)
        self.assertIs(raised.exception.__cause__, failure)

    def test_cancellable_download_uses_explicit_adapter_boundary(self):
        downloader = Mock()
        downloader.download_video_cancellable.return_value = DownloadOutcome(
            video_id="video",
            title="Example video",
            source_url="https://example.test",
            artifacts=DownloadedArtifacts(
                video=Path("/archive/video.mkv"),
                metadata=(),
                thumbnails=(),
            ),
        )
        token = CancellationToken()

        result = VideoDownloadService(downloader).download(
            "https://example.test",
            cancellation_token=token,
        )

        self.assertEqual(result.video_id, "video")
        self.assertEqual(result.title, "Example video")
        downloader.download_video.assert_not_called()
        downloader.download_video_cancellable.assert_called_once_with(
            url="https://example.test",
            cancellation_token=token,
        )

    def test_typed_error_preserves_original_traceback(self):
        downloader = Mock()

        def fail_download(*, url):
            raise OSError(f"adapter failure for {url}")

        downloader.download_video.side_effect = fail_download

        with self.assertRaises(VideoDownloadError) as raised:
            VideoDownloadService(downloader).download(
                "https://example.test",
            )

        cause = raised.exception.__cause__
        self.assertIsInstance(cause, OSError)
        self.assertIsNotNone(cause.__traceback__)
        formatted = "".join(traceback.format_exception(raised.exception))
        self.assertIn("fail_download", formatted)
        self.assertIn(
            "The above exception was the direct cause",
            formatted,
        )

    def test_unexpected_download_failure_is_not_translated(self):
        downloader = Mock()
        failure = RuntimeError("programming error")
        downloader.download_video.side_effect = failure

        with self.assertRaises(RuntimeError) as raised:
            VideoDownloadService(downloader).download(
                "https://example.test",
            )

        self.assertIs(raised.exception, failure)

    def test_unexpected_check_failure_is_not_translated(self):
        downloader = Mock()
        failure = AttributeError("broken adapter implementation")
        downloader.check_availability.side_effect = failure

        with self.assertRaises(AttributeError) as raised:
            VideoDownloadService(downloader).check(
                "https://example.test",
            )

        self.assertIs(raised.exception, failure)


class TwitchDownloadServiceTest(unittest.TestCase):
    def test_offline_error_is_translated(self):
        downloader = Mock()
        error = yt_dlp.utils.DownloadError("extract failed")
        error.exc_info = (
            None,
            RuntimeError("The channel is not currently live"),
            None,
        )
        downloader.check_availability.side_effect = error

        with self.assertRaises(TwitchStreamOffline):
            TwitchDownloadService(downloader).check(
                "https://www.twitch.tv/channel",
            )

        downloader.check_availability.assert_called_once_with(
            url="https://www.twitch.tv/channel",
        )

    def test_other_error_is_propagated(self):
        downloader = Mock()
        error = yt_dlp.utils.DownloadError("network failed")
        downloader.check_availability.side_effect = error

        with self.assertRaises(VideoCheckError) as raised:
            TwitchDownloadService(downloader).check(
                "https://www.twitch.tv/channel",
            )

        self.assertIs(raised.exception.original_error, error)
        self.assertIs(raised.exception.__cause__, error)

    def test_unexpected_error_is_not_translated(self):
        downloader = Mock()
        error = TypeError("broken adapter implementation")
        downloader.check_availability.side_effect = error

        with self.assertRaises(TypeError) as raised:
            TwitchDownloadService(downloader).check(
                "https://www.twitch.tv/channel",
            )

        self.assertIs(raised.exception, error)

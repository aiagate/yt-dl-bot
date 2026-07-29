import unittest
from pathlib import Path
from unittest.mock import call

from download_adapter_test_support import DownloadAdapterTestCase

from yt_dl_bot.artifact_discovery import DownloadedArtifacts
from yt_dl_bot.yt_dlp_downloader import YtDlpDownloader


class YtDlpDownloaderBoundaryTest(DownloadAdapterTestCase, unittest.TestCase):
    downloader_type = YtDlpDownloader

    def test_download_moves_only_artifacts_reported_as_existing(self):
        stem = Path("/tmp/downloads/2026-07-28-0905_video：id")
        self.download_info.update(
            {
                "ext": "webm",
                "filepath": str(Path(f"{stem}.webm")),
                "infojson_filename": str(Path(f"{stem}.info.json")),
                "thumbnails": [
                    {"filepath": str(Path(f"{stem}.jpg")), "ext": "jpg"},
                ],
            }
        )
        self.existing_paths = {
            Path(f"{stem}.webm"),
            Path(f"{stem}.info.json"),
            Path(f"{stem}.jpg"),
        }

        result = self.downloader.download_video(
            "https://www.twitch.tv/channel",
        )

        self.assertEqual(result.video_id, "video:id")
        self.assertEqual(result.title, "Example video")
        self.assertEqual(
            result.source_url,
            "https://www.twitch.tv/channel",
        )
        self.assertEqual(
            result.artifacts,
            DownloadedArtifacts(
                video=Path(f"/archive/{stem.name}.webm"),
                metadata=(Path(f"/archive/metadata/{stem.name}.info.json"),),
                thumbnails=(Path(f"/archive/thumbnail/{stem.name}.jpg"),),
            ),
        )
        self.assertEqual(
            self.ydl_instances[-1].options["outtmpl"],
            f"{stem}.%(ext)s",
        )
        self.assertEqual(
            self.move.call_args_list,
            [
                call(Path(f"{stem}.webm"), Path("/archive")),
                call(Path(f"{stem}.info.json"), Path("/archive/metadata")),
                call(Path(f"{stem}.jpg"), Path("/archive/thumbnail")),
            ],
        )

    def test_build_options_uses_injected_cookie_existence_check(self):
        self.existing_paths.add(Path("cookie/cookies.txt"))

        options = self.downloader.engine.build_options("/tmp/video.%(ext)s")

        self.assertEqual(options["cookiefile"], "cookie/cookies.txt")

    def test_download_options_are_fresh_for_each_call(self):
        first = self.downloader.engine.build_options("/tmp/first.%(ext)s")
        first["postprocessors"].append({"key": "test-only"})

        second = self.downloader.engine.build_options("/tmp/second.%(ext)s")

        self.assertNotIn(
            {"key": "test-only"},
            second["postprocessors"],
        )

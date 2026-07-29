import datetime
import unittest
from pathlib import Path
from unittest.mock import Mock, call

from yt_dl_bot.artifact_discovery import DownloadedArtifacts
from yt_dl_bot.download_service import (
    DownloadDependencies,
)
from yt_dl_bot.yt_dlp_downloader import YtDlpDownloader


class FakeYoutubeDL:
    def __init__(self, info, options=None):
        self.info = info
        self.options = options
        self.extract_calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def extract_info(self, url, download):
        self.extract_calls.append((url, download))
        return self.info.copy()

    def prepare_filename(self, info):
        template = self.options["outtmpl"]
        return template.replace("%(ext)s", info.get("ext", "mp4"))


class DownloadAdapterTestCase:
    downloader_type = None

    def setUp(self):
        stem = Path("/tmp/downloads/2026-07-28-0905_video：id")
        self.download_info = {
            "id": "video:id",
            "title": "Example video",
            "ext": "mp4",
            "filepath": str(Path(f"{stem}.mp4")),
            "infojson_filename": str(Path(f"{stem}.info.json")),
            "thumbnails": [
                {"filepath": str(Path(f"{stem}.webp")), "ext": "webp"},
            ],
        }
        self.downloaded_info = None
        self.ydl_instances = []
        self.existing_paths = {
            Path(f"{stem}.mp4"),
            Path(f"{stem}.info.json"),
            Path(f"{stem}.webp"),
        }
        self.mkdir = Mock(
            side_effect=lambda path, **_kwargs: self.existing_paths.add(path),
        )
        self.move = Mock()
        self.sleep = Mock()

        def ydl_factory(options=None):
            info = (
                self.download_info
                if options is None or self.downloaded_info is None
                else self.downloaded_info
            )
            instance = FakeYoutubeDL(info, options)
            self.ydl_instances.append(instance)
            return instance

        self.dependencies = DownloadDependencies(
            ydl_factory=ydl_factory,
            now=lambda: datetime.datetime(2026, 7, 28, 9, 5),
            sleep=self.sleep,
            path_exists=lambda path: path in self.existing_paths,
            make_directory=self.mkdir,
            move=self.move,
            tmp_path="/tmp/downloads",
            save_path="/archive",
        )
        self.downloader = self.downloader_type(self.dependencies)

    def test_get_info_uses_injected_ytdl_without_downloading(self):
        info = self.downloader.get_info("https://example.test/video")

        self.assertEqual(info, self.download_info)
        self.assertIsNone(self.ydl_instances[0].options)
        self.assertEqual(
            self.ydl_instances[0].extract_calls,
            [("https://example.test/video", False)],
        )


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

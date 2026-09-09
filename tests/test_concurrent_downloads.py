"""Concurrent download requests must not share files or overwrite stored artifacts."""

import datetime
import shutil
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

from yt_dl_bot.cancellation import CancellationToken, DownloadCancelled
from yt_dl_bot.download_engine import DownloadEngine, youtube_download_policy
from yt_dl_bot.download_primitives import DownloadDependencies


class ConcurrentDownloadTest(unittest.TestCase):
    def make_engine(self, root, extract):
        def factory(options=None):
            ydl = Mock()
            ydl.__enter__ = Mock(return_value=ydl)
            ydl.__exit__ = Mock(return_value=False)
            ydl.extract_info.side_effect = lambda url, download: extract(options, url, download)
            return ydl

        return DownloadEngine(
            DownloadDependencies(
                ydl_factory=factory,
                now=lambda: datetime.datetime(2026, 7, 28, 9, 5),
                sleep=Mock(),
                path_exists=Path.exists,
                make_directory=Path.mkdir,
                move=shutil.move,
                tmp_path=root / "tmp",
                save_path=root / "archive",
            ),
            youtube_download_policy(),
        )

    @staticmethod
    def write_artifacts(options, contents):
        template = options["outtmpl"]
        video, metadata, thumbnail = (
            Path(template.replace("%(ext)s", ext)) for ext in ("mp4", "info.json", "webp")
        )
        for path in (video, metadata, thumbnail):
            path.write_text(contents)
        return {
            "id": "video",
            "title": "Video",
            "filepath": str(video),
            "infojson_filename": str(metadata),
            "thumbnails": [{"filepath": str(thumbnail)}],
        }

    def test_same_video_downloads_are_isolated_and_only_one_complete_set_is_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            downloaded = threading.Barrier(2)
            request_paths = []

            def extract(options, url, download):
                if not download:
                    return {"id": "video"}
                request_paths.append(Path(options["outtmpl"]).parent)
                info = self.write_artifacts(options, url)
                downloaded.wait(timeout=5)
                return info

            # Separate engines/stores mirror independent command adapters.
            engines = [self.make_engine(root, extract) for _ in range(2)]
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(engine.download_video, f"request-{index}")
                    for index, engine in enumerate(engines)
                ]
                results, failures = [], []
                for future in futures:
                    try:
                        results.append(future.result(timeout=5))
                    except shutil.Error as error:
                        failures.append(error)

            self.assertEqual(len(set(request_paths)), 2)
            self.assertEqual(len(results), 1)
            self.assertEqual(len(failures), 1)
            self.assertIn("Destination path already exists", str(failures[0]))
            saved = results[0].artifacts
            winner = saved.video.read_text()
            self.assertEqual(saved.video.name, "2026-07-28-0905_video.mp4")
            self.assertEqual(
                [path.read_text() for path in (*saved.metadata, *saved.thumbnails)],
                [winner, winner],
            )
            # Successful request is cleaned, rejected request remains recoverable.
            remaining = list((root / "tmp").iterdir())
            self.assertEqual(len(remaining), 1)
            self.assertEqual(len(list(remaining[0].iterdir())), 3)
            self.assertNotEqual(next(remaining[0].iterdir()).read_text(), winner)

    def test_cancelled_or_failed_download_retains_partial_files(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                token = CancellationToken()

                def extract(options, _url, download, token=token, cancel=cancel):
                    if not download:
                        return {"id": "video"}
                    info = self.write_artifacts(options, "recoverable")
                    if cancel:
                        token.cancel()
                        return info
                    raise OSError("download interrupted")

                engine = self.make_engine(root, extract)
                with self.assertRaises(DownloadCancelled if cancel else OSError):
                    engine.download_video("video", cancellation_token=token)
                self.assertEqual(len(list((root / "tmp").glob("*/*"))), 3)
                self.assertFalse((root / "archive").exists())

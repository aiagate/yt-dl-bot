import datetime
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import yt_dlp


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = PROJECT_ROOT / 'source'
sys.path.insert(0, str(SOURCE_PATH))

from artifact_discovery import DownloadedArtifacts
from download_engine import (
    DownloadEngine,
    build_output_name,
    generic_download_policy,
    youtube_download_policy,
)
from download_service import DownloadDependencies, RetryPolicy
from youtubemodule import YoutubeModule
from ytdlpmodule import YtdlpModule


def dependencies(existing=()):
    existing = {Path(path) for path in existing}
    return DownloadDependencies(
        ydl_factory=Mock(),
        now=lambda: datetime.datetime(2026, 7, 28, 9, 5),
        sleep=Mock(),
        path_exists=lambda path: path in existing,
        make_directory=Mock(),
        move=Mock(),
        tmp_path=Path('/tmp/downloads'),
        save_path=Path('/archive'),
    )


class DownloadPolicyTest(unittest.TestCase):
    def test_youtube_policy_declares_retry_and_required_outputs(self):
        retry = RetryPolicy(max_attempts=3, max_wait_seconds=60)
        policy = youtube_download_policy(retry)

        self.assertIs(policy.retry_policy, retry)
        self.assertTrue(policy.scheduled_notice)
        self.assertTrue(policy.require_metadata)
        self.assertTrue(policy.require_thumbnail)
        self.assertTrue(policy.live_from_start)
        self.assertFalse(policy.use_cookie_file)

    def test_generic_policy_declares_optional_sidecars_and_cookie(self):
        policy = generic_download_policy()

        self.assertIsNone(policy.retry_policy)
        self.assertFalse(policy.scheduled_notice)
        self.assertFalse(policy.require_metadata)
        self.assertFalse(policy.require_thumbnail)
        self.assertFalse(policy.live_from_start)
        self.assertTrue(policy.use_cookie_file)

    def test_policy_options_only_contain_their_site_specific_values(self):
        youtube = DownloadEngine(
            dependencies(existing={'cookie/cookies.txt'}),
            youtube_download_policy(),
        )
        generic = DownloadEngine(
            dependencies(existing={'cookie/cookies.txt'}),
            generic_download_policy(),
        )

        youtube_options = youtube.build_options('/tmp/video.%(ext)s')
        generic_options = generic.build_options('/tmp/video.%(ext)s')

        self.assertTrue(youtube_options['live_from_start'])
        self.assertNotIn('cookiefile', youtube_options)
        self.assertNotIn('live_from_start', generic_options)
        self.assertEqual(
            generic_options['cookiefile'],
            'cookie/cookies.txt',
        )

    def test_shared_output_naming_preserves_sanitization(self):
        name = build_output_name(
            {'id': 'video:id?part'},
            datetime.datetime(2026, 7, 28, 9, 5),
        )

        self.assertEqual(name, '2026-07-28-0905_video：id？part')

    def test_scheduled_notice_is_youtube_only(self):
        error = yt_dlp.utils.DownloadError(
            'This live event will begin in 2 hours.',
        )
        youtube = YoutubeModule(dependencies())
        generic = YtdlpModule(dependencies())
        youtube.get_info = Mock(side_effect=error)
        generic.get_info = Mock(side_effect=error)

        self.assertIn(
            'Will be downloaded in',
            youtube.data_check('https://youtu.be/video'),
        )
        with self.assertRaises(yt_dlp.utils.DownloadError):
            generic.data_check('https://example.test/video')


class ArtifactStorageTest(unittest.TestCase):
    def test_partial_move_is_rolled_back_when_later_move_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tmp_path = root / 'tmp'
            save_path = root / 'archive'
            tmp_path.mkdir()
            video = tmp_path / 'video.mp4'
            metadata = tmp_path / 'video.info.json'
            thumbnail = tmp_path / 'video.webp'
            for artifact in (video, metadata, thumbnail):
                artifact.write_text(artifact.name)

            move_count = 0

            def fail_on_third_move(source, destination):
                nonlocal move_count
                move_count += 1
                if move_count == 3:
                    raise OSError('injected thumbnail move failure')
                return shutil.move(source, destination)

            injected_dependencies = DownloadDependencies(
                ydl_factory=Mock(),
                now=lambda: datetime.datetime(2026, 7, 28, 9, 5),
                sleep=Mock(),
                path_exists=Path.exists,
                make_directory=Path.mkdir,
                move=fail_on_third_move,
                tmp_path=tmp_path,
                save_path=save_path,
            )
            engine = DownloadEngine(
                injected_dependencies,
                youtube_download_policy(),
            )
            artifacts = DownloadedArtifacts(
                video=video,
                metadata=(metadata,),
                thumbnails=(thumbnail,),
            )

            with self.assertRaisesRegex(
                OSError,
                'injected thumbnail move failure',
            ):
                engine._move_artifacts(artifacts)

            self.assertTrue(all(
                artifact.exists()
                for artifact in (video, metadata, thumbnail)
            ))
            self.assertFalse((save_path / video.name).exists())
            self.assertFalse(
                (save_path / 'metadata' / metadata.name).exists(),
            )
            self.assertFalse(
                (save_path / 'thumbnail' / thumbnail.name).exists(),
            )

    def test_artifacts_are_moved_to_the_existing_directory_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tmp_path = root / 'tmp'
            save_path = root / 'archive'
            tmp_path.mkdir()
            video = tmp_path / 'video.mp4'
            metadata = tmp_path / 'video.info.json'
            thumbnail = tmp_path / 'video.webp'
            for artifact in (video, metadata, thumbnail):
                artifact.write_text(artifact.name)
            injected_dependencies = DownloadDependencies(
                ydl_factory=Mock(),
                now=lambda: datetime.datetime(2026, 7, 28, 9, 5),
                sleep=Mock(),
                path_exists=Path.exists,
                make_directory=Path.mkdir,
                move=shutil.move,
                tmp_path=tmp_path,
                save_path=save_path,
            )
            engine = DownloadEngine(
                injected_dependencies,
                youtube_download_policy(),
            )

            engine._move_artifacts(DownloadedArtifacts(
                video=video,
                metadata=(metadata,),
                thumbnails=(thumbnail,),
            ))

            self.assertTrue((save_path / video.name).exists())
            self.assertTrue(
                (save_path / 'metadata' / metadata.name).exists(),
            )
            self.assertTrue(
                (save_path / 'thumbnail' / thumbnail.name).exists(),
            )

    def test_existing_destination_is_detected_before_any_move(self):
        injected_dependencies = dependencies(
            existing={
                '/archive',
                '/archive/metadata',
                '/archive/thumbnail',
                '/archive/metadata/video.info.json',
            },
        )
        engine = DownloadEngine(
            injected_dependencies,
            youtube_download_policy(),
        )

        with self.assertRaisesRegex(
            shutil.Error,
            'Destination path already exists',
        ):
            engine._move_artifacts(DownloadedArtifacts(
                video=Path('/tmp/downloads/video.mp4'),
                metadata=(Path('/tmp/downloads/video.info.json'),),
                thumbnails=(Path('/tmp/downloads/video.webp'),),
            ))

        injected_dependencies.move.assert_not_called()


class FacadeStructureTest(unittest.TestCase):
    def test_facades_keep_public_api_and_explicit_policies(self):
        youtube = YoutubeModule(dependencies())
        generic = YtdlpModule(dependencies())

        expected_methods = (
            'data_check',
            'download_video',
            'get_info',
            'live_timer',
            'ops',
            'get_videoid',
        )
        for facade in (youtube, generic):
            with self.subTest(facade=type(facade).__name__):
                self.assertTrue(all(
                    callable(getattr(facade, method))
                    for method in expected_methods
                ))
                self.assertIsInstance(facade.engine, DownloadEngine)

        self.assertTrue(youtube.engine.policy.live_from_start)
        self.assertTrue(generic.engine.policy.use_cookie_file)

    def test_shared_download_implementation_is_not_duplicated_in_facades(self):
        facade_paths = (
            SOURCE_PATH / 'youtubemodule.py',
            SOURCE_PATH / 'ytdlpmodule.py',
        )
        forbidden = (
            'yt_dlp',
            'discover_download_artifacts',
            'FFmpegVideoConvertor',
            '.ydl_factory(',
            '.move(',
            'bestvideo+bestaudio/best',
        )

        for path in facade_paths:
            source = path.read_text()
            with self.subTest(path=path.name):
                self.assertIn('DownloadEngine', source)
                for marker in forbidden:
                    self.assertNotIn(marker, source)


if __name__ == '__main__':
    unittest.main()

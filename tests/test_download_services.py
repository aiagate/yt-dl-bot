import datetime
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, call

import yt_dlp


SOURCE_PATH = Path(__file__).resolve().parents[1] / 'source'
sys.path.insert(0, str(SOURCE_PATH))

from download_service import (
    DownloadDependencies,
    DownloadRetryLimitExceeded,
    PermanentDownloadError,
    RetryDecision,
    RetryPolicy,
    RetryStatus,
)
from youtubemodule import YoutubeModule
from ytdlpmodule import YtdlpModule


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


class DownloadModuleTestCase:
    module_type = None

    def setUp(self):
        self.download_info = {
            'id': 'video:id',
            'title': 'Example video',
        }
        self.ydl_instances = []
        self.existing_paths = set()
        self.mkdir = Mock(
            side_effect=lambda path, **kwargs: self.existing_paths.add(path),
        )
        self.move = Mock()
        self.sleep = Mock()

        def ydl_factory(options=None):
            instance = FakeYoutubeDL(self.download_info, options)
            self.ydl_instances.append(instance)
            return instance

        self.dependencies = DownloadDependencies(
            ydl_factory=ydl_factory,
            now=lambda: datetime.datetime(2026, 7, 28, 9, 5),
            sleep=self.sleep,
            path_exists=lambda path: path in self.existing_paths,
            make_directory=self.mkdir,
            move=self.move,
            tmp_path='/tmp/downloads',
            save_path='/archive',
        )
        self.module = self.module_type(self.dependencies)

    def test_get_info_uses_injected_ytdl_without_downloading(self):
        info = self.module.get_info('https://example.test/video')

        self.assertEqual(info, self.download_info)
        self.assertIsNone(self.ydl_instances[0].options)
        self.assertEqual(
            self.ydl_instances[0].extract_calls,
            [('https://example.test/video', False)],
        )


class YoutubeModuleBoundaryTest(DownloadModuleTestCase, unittest.TestCase):
    module_type = YoutubeModule

    def test_download_uses_injected_clock_paths_and_artifact_mover(self):
        info = self.module.download_video('https://youtu.be/video')

        self.assertEqual(info, self.download_info)
        download = self.ydl_instances[-1]
        self.assertEqual(
            download.options['outtmpl'],
            '/tmp/downloads/2026-07-28-0905_video：id.%(ext)s',
        )
        self.assertEqual(
            download.extract_calls,
            [('https://youtu.be/video', True)],
        )
        self.assertEqual(
            self.move.call_args_list,
            [
                call(
                    Path('/tmp/downloads/2026-07-28-0905_video：id.mp4'),
                    Path('/archive'),
                ),
                call(
                    Path('/tmp/downloads/2026-07-28-0905_video：id.info.json'),
                    Path('/archive/metadata'),
                ),
                call(
                    Path('/tmp/downloads/2026-07-28-0905_video：id.webp'),
                    Path('/archive/thumbnail'),
                ),
            ],
        )
        self.mkdir.assert_has_calls([
            call(Path('/tmp/downloads'), parents=True, exist_ok=True),
            call(Path('/archive'), parents=True, exist_ok=True),
            call(Path('/archive/metadata'), parents=True, exist_ok=True),
            call(Path('/archive/thumbnail'), parents=True, exist_ok=True),
        ])

    def test_trailing_slash_does_not_change_configured_paths(self):
        with_slashes = DownloadDependencies(
            ydl_factory=self.dependencies.ydl_factory,
            now=self.dependencies.now,
            sleep=self.sleep,
            path_exists=self.dependencies.path_exists,
            make_directory=self.mkdir,
            move=self.move,
            tmp_path='/tmp/downloads/',
            save_path='/archive/',
        )

        self.assertEqual(
            with_slashes.tmp_path,
            self.dependencies.tmp_path,
        )
        self.assertEqual(
            with_slashes.save_path,
            self.dependencies.save_path,
        )

    def test_download_retries_with_injected_sleep(self):
        error = yt_dlp.utils.DownloadError(
            'This live event will begin in 1 minutes.',
        )
        self.module.get_info = Mock(
            side_effect=[error, self.download_info],
        )

        self.module.download_video('https://youtu.be/video')

        self.sleep.assert_called_once_with(30.0)
        self.assertEqual(self.module.get_info.call_count, 2)

    def test_permanent_download_error_fails_without_sleeping(self):
        error = yt_dlp.utils.DownloadError('Video unavailable')
        self.module.get_info = Mock(side_effect=error)

        with self.assertRaises(PermanentDownloadError) as raised:
            self.module.download_video('https://youtu.be/video')

        self.assertIs(raised.exception.original_error, error)
        self.assertEqual(raised.exception.attempts, 1)
        self.sleep.assert_not_called()

    def test_retry_attempt_limit_is_enforced(self):
        error = yt_dlp.utils.DownloadError(
            'This live event will begin in 1 minutes.',
        )
        self.module = YoutubeModule(
            self.dependencies,
            retry_policy=RetryPolicy(
                max_attempts=2,
                max_wait_seconds=3600,
            ),
        )
        self.module.get_info = Mock(side_effect=error)

        with self.assertRaises(DownloadRetryLimitExceeded) as raised:
            self.module.download_video('https://youtu.be/video')

        self.assertEqual(raised.exception.attempts, 2)
        self.assertEqual(raised.exception.waited_seconds, 30.0)
        self.sleep.assert_called_once_with(30.0)

    def test_total_wait_limit_is_enforced_before_sleep(self):
        error = yt_dlp.utils.DownloadError(
            'This live event will begin in 2 hours.',
        )
        self.module = YoutubeModule(
            self.dependencies,
            retry_policy=RetryPolicy(
                max_attempts=10,
                max_wait_seconds=3600,
            ),
        )
        self.module.get_info = Mock(side_effect=error)

        with self.assertRaises(DownloadRetryLimitExceeded) as raised:
            self.module.download_video('https://youtu.be/video')

        self.assertEqual(raised.exception.attempts, 1)
        self.assertEqual(raised.exception.waited_seconds, 0)
        self.sleep.assert_not_called()

    def test_live_timer_retains_retry_delay_compatibility(self):
        error = yt_dlp.utils.DownloadError(
            'Premieres in 7 hours.',
        )

        self.assertEqual(self.module.live_timer(error), 23400.0)


class RetryPolicyTest(unittest.TestCase):
    def test_distinguishes_retryable_and_permanent_failures(self):
        policy = RetryPolicy()

        retryable = policy.decide(yt_dlp.utils.DownloadError(
            'This live event will begin shortly.',
        ))
        permanent = policy.decide(
            yt_dlp.utils.ExtractorError('Unsupported URL'),
        )

        self.assertEqual(
            retryable,
            RetryDecision(RetryStatus.RETRYABLE, 15),
        )
        self.assertEqual(
            permanent,
            RetryDecision(RetryStatus.PERMANENT_FAILURE),
        )

    def test_rejects_invalid_retry_limits(self):
        with self.assertRaises(ValueError):
            RetryPolicy(max_attempts=0)
        with self.assertRaises(ValueError):
            RetryPolicy(max_wait_seconds=-1)


class YtdlpModuleBoundaryTest(DownloadModuleTestCase, unittest.TestCase):
    module_type = YtdlpModule

    def test_download_moves_only_artifacts_reported_as_existing(self):
        stem = Path('/tmp/downloads/2026-07-28-0905_video：id')
        self.existing_paths.update({
            Path(f'{stem}.mp4'),
            Path(f'{stem}.info.json'),
            Path(f'{stem}.jpg'),
        })

        info = self.module.download_video('https://www.twitch.tv/channel')

        self.assertEqual(info, self.download_info)
        self.assertEqual(
            self.ydl_instances[-1].options['outtmpl'],
            f'{stem}.%(ext)s',
        )
        self.assertEqual(
            self.move.call_args_list,
            [
                call(Path(f'{stem}.mp4'), Path('/archive')),
                call(Path(f'{stem}.info.json'), Path('/archive/metadata')),
                call(Path(f'{stem}.jpg'), Path('/archive/thumbnail')),
            ],
        )

    def test_ops_uses_injected_cookie_existence_check(self):
        self.existing_paths.add(Path('cookie/cookies.txt'))

        options = self.module.ops('/tmp/video.%(ext)s')

        self.assertEqual(options['cookiefile'], 'cookie/cookies.txt')


if __name__ == '__main__':
    unittest.main()

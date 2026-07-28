import datetime
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

import yt_dlp


SOURCE_PATH = Path(__file__).resolve().parents[1] / 'source'
sys.path.insert(0, str(SOURCE_PATH))

REQUIRED_ENVIRONMENT = {
    'DISCORD_KEY': 'discord-token',
    'LOG_CHANNEL': '1',
    'VIDEO_OUTPUT_CHANNEL': '2',
    'HIGHLIGHT_OUTPUT_CHANNEL': '3',
    'DOWNLOAD_CHANNEL': '4',
    'HIGHLIGHT_CHANNEL': '5',
}

with patch.dict(os.environ, REQUIRED_ENVIRONMENT):
    from download_service import DownloadDependencies
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
        self.mkdir = Mock(side_effect=self.existing_paths.add)
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
            tmp_path='/tmp/downloads/',
            save_path='/archive/',
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
                    '/tmp/downloads/2026-07-28-0905_video：id.mp4',
                    '/archive/',
                ),
                call(
                    '/tmp/downloads/2026-07-28-0905_video：id.info.json',
                    '/archive/metadata/',
                ),
                call(
                    '/tmp/downloads/2026-07-28-0905_video：id.webp',
                    '/archive/thumbnail/',
                ),
            ],
        )
        self.mkdir.assert_has_calls([
            call('/tmp/downloads/'),
            call('/archive/'),
            call('/archive/metadata/'),
            call('/archive/thumbnail/'),
        ])

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


class YtdlpModuleBoundaryTest(DownloadModuleTestCase, unittest.TestCase):
    module_type = YtdlpModule

    def test_download_moves_only_artifacts_reported_as_existing(self):
        stem = '/tmp/downloads/2026-07-28-0905_video：id'
        self.existing_paths.update({
            stem + '.mp4',
            stem + '.info.json',
            stem + '.jpg',
        })

        info = self.module.download_video('https://www.twitch.tv/channel')

        self.assertEqual(info, self.download_info)
        self.assertEqual(
            self.ydl_instances[-1].options['outtmpl'],
            stem + '.%(ext)s',
        )
        self.assertEqual(
            self.move.call_args_list,
            [
                call(stem + '.mp4', '/archive/'),
                call(stem + '.info.json', '/archive/metadata/'),
                call(stem + '.jpg', '/archive/thumbnail/'),
            ],
        )

    def test_ops_uses_injected_cookie_existence_check(self):
        self.existing_paths.add('cookie/cookies.txt')

        options = self.module.ops('/tmp/video.%(ext)s')

        self.assertEqual(options['cookiefile'], 'cookie/cookies.txt')


if __name__ == '__main__':
    unittest.main()

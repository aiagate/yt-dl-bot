import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


SOURCE_PATH = Path(__file__).resolve().parents[1] / 'source'
sys.path.insert(0, str(SOURCE_PATH))

for key, value in {
    'DISCORD_KEY': 'test-token',
    'YOUTUBE_API_KEY': 'test-api-key',
    'DB_USERNAME': 'test-user',
    'DB_PASSWORD': 'test-password',
    'LOG_CHANNEL': '1',
    'VIDEO_OUTPUT_CHANNEL': '2',
    'HIGHLIGHT_OUTPUT_CHANNEL': '3',
    'SEARCH_OUTPUT_CHANNEL': '4',
    'DOWNLOAD_CHANNEL': '5',
    'HIGHLIGHT_CHANNEL': '6',
    'SEARCH_CHANNEL': '7',
}.items():
    os.environ.setdefault(key, value)

from chatdatacollector import ChatDataCollector


class ChatDataCollectorTest(unittest.TestCase):
    def setUp(self):
        self.collector = object.__new__(ChatDataCollector)
        self.collector.logger = MagicMock()

    @patch('chatdatacollector.time.sleep')
    @patch('chatdatacollector.yt_dlp.YoutubeDL')
    def test_extract_info_retries_and_returns_success(self, youtube_dl, sleep):
        downloader = youtube_dl.return_value.__enter__.return_value
        downloader.extract_info.side_effect = [
            RuntimeError('temporary failure'),
            {'id': 'video-id'},
        ]

        result = self.collector._extract_info(
            'https://example.invalid/video',
            retries=2,
            retry_delay=0,
        )

        self.assertEqual(result, {'id': 'video-id'})
        self.assertEqual(downloader.extract_info.call_count, 2)
        sleep.assert_called_once_with(0)

    @patch('chatdatacollector.time.sleep')
    @patch('chatdatacollector.yt_dlp.YoutubeDL')
    def test_extract_info_raises_last_error(self, youtube_dl, sleep):
        downloader = youtube_dl.return_value.__enter__.return_value
        downloader.extract_info.side_effect = RuntimeError('permanent failure')

        with self.assertRaisesRegex(RuntimeError, 'permanent failure'):
            self.collector._extract_info(
                'https://example.invalid/video',
                retries=2,
                retry_delay=0,
            )

        self.assertEqual(downloader.extract_info.call_count, 2)
        sleep.assert_called_once_with(0)

    def test_get_videolist_handles_empty_channel(self):
        self.collector._extract_info = MagicMock(return_value={'entries': []})
        self.collector.ytdl_ops = {}

        self.assertIsNone(self.collector.get_videolist('channel-id'))


if __name__ == '__main__':
    unittest.main()

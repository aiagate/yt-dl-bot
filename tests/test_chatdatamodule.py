import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SOURCE_PATH = Path(__file__).resolve().parents[1] / 'source'
sys.path.insert(0, str(SOURCE_PATH))

for key, value in {
    'DISCORD_KEY': 'test-token',
    'LOG_CHANNEL': '1',
    'VIDEO_OUTPUT_CHANNEL': '2',
    'HIGHLIGHT_OUTPUT_CHANNEL': '3',
    'DOWNLOAD_CHANNEL': '4',
    'HIGHLIGHT_CHANNEL': '5',
}.items():
    os.environ.setdefault(key, value)

from chatdatamodule import ChatDataModule


class ChatDataModuleTest(unittest.TestCase):
    def test_elapsed_seconds(self):
        self.assertEqual(ChatDataModule._elapsed_seconds('01:02:03'), 3723)
        self.assertEqual(ChatDataModule._elapsed_seconds('02:03'), 123)
        self.assertEqual(ChatDataModule._elapsed_seconds('12'), 12)
        self.assertIsNone(ChatDataModule._elapsed_seconds('invalid'))

    def test_count_score_does_not_persist_comments(self):
        module = ChatDataModule('video-id')
        scores = module.count_score([0, 10, 20])

        self.assertEqual(len(scores), 3)
        self.assertEqual(scores[0], 0)
        self.assertGreater(scores[2], scores[1])

    def test_get_highlight_uses_in_memory_counts(self):
        module = ChatDataModule('video-id')
        with (
            patch.object(module, 'collect_comment_counts', return_value=[0, 0, 20]),
            patch.object(module, 'plot_peak'),
        ):
            highlights = module.get_highlight()

        self.assertEqual(highlights, [[30, 'https://youtu.be/video-id?t=30s']])


if __name__ == '__main__':
    unittest.main()

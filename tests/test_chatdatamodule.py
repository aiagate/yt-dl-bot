import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SOURCE_PATH = Path(__file__).resolve().parents[1] / 'source'
sys.path.insert(0, str(SOURCE_PATH))

from chatdatamodule import ChatDataModule


class ChatDataModuleTest(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(TMP_PATH='downloads/cache/')

    def test_elapsed_seconds(self):
        self.assertEqual(ChatDataModule._elapsed_seconds('01:02:03'), 3723)
        self.assertEqual(ChatDataModule._elapsed_seconds('02:03'), 123)
        self.assertEqual(ChatDataModule._elapsed_seconds('12'), 12)
        self.assertIsNone(ChatDataModule._elapsed_seconds('invalid'))

    def test_count_score_does_not_persist_comments(self):
        module = ChatDataModule('video-id', settings=self.settings)
        scores = module.count_score([0, 10, 20])

        self.assertEqual(len(scores), 3)
        self.assertEqual(scores[0], 0)
        self.assertGreater(scores[2], scores[1])

    def test_get_highlight_uses_in_memory_counts(self):
        module = ChatDataModule('video-id', settings=self.settings)
        with (
            patch.object(module, 'collect_comment_counts', return_value=[0, 0, 20]),
            patch.object(module, 'plot_peak'),
        ):
            highlights = module.get_highlight()

        self.assertEqual(highlights, [[30, 'https://youtu.be/video-id?t=30s']])


if __name__ == '__main__':
    unittest.main()

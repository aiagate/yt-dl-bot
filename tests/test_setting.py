import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SOURCE_PATH = Path(__file__).resolve().parents[1] / 'source'
sys.path.insert(0, str(SOURCE_PATH))

from setting import Settings


class SettingsTest(unittest.TestCase):
    def test_required_values_are_loaded_from_environment(self):
        environment = {
            'DISCORD_KEY': 'discord-token',
            'LOG_CHANNEL': '1',
            'VIDEO_OUTPUT_CHANNEL': '2',
            'HIGHLIGHT_OUTPUT_CHANNEL': '3',
            'DOWNLOAD_CHANNEL': '4',
            'HIGHLIGHT_CHANNEL': '5',
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = Settings(_env_file=None)

        self.assertEqual(settings.LOG_CHANNEL, 1)
        self.assertEqual(settings.DISCORD_KEY.get_secret_value(), 'discord-token')


if __name__ == '__main__':
    unittest.main()

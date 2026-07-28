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
            'YOUTUBE_API_KEY': 'youtube-token',
            'DB_USERNAME': 'app-user',
            'DB_PASSWORD': 'db-password',
            'LOG_CHANNEL': '1',
            'VIDEO_OUTPUT_CHANNEL': '2',
            'HIGHLIGHT_OUTPUT_CHANNEL': '3',
            'SEARCH_OUTPUT_CHANNEL': '4',
            'DOWNLOAD_CHANNEL': '5',
            'HIGHLIGHT_CHANNEL': '6',
            'SEARCH_CHANNEL': '7',
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = Settings(_env_file=None)

        self.assertEqual(settings.DB_HOSTNAME, 'database')
        self.assertEqual(settings.LOG_CHANNEL, 1)
        self.assertEqual(settings.DISCORD_KEY.get_secret_value(), 'discord-token')
        self.assertEqual(settings.DB_PASSWORD.get_secret_value(), 'db-password')


if __name__ == '__main__':
    unittest.main()

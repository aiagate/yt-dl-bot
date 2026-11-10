import os
import unittest
from pathlib import Path
from unittest.mock import patch

from yt_dl_bot.setting import Settings


class SettingsTest(unittest.TestCase):
    def test_required_values_are_loaded_from_environment(self):
        environment = {
            "DISCORD_KEY": "discord-token",
            "LOG_CHANNEL": "1",
            "VIDEO_OUTPUT_CHANNEL": "2",
            "DOWNLOAD_CHANNEL": "4",
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = Settings(_env_file=None)

        self.assertEqual(settings.LOG_CHANNEL, 1)
        self.assertEqual(settings.DISCORD_KEY.get_secret_value(), "discord-token")
        self.assertIsInstance(settings.SAVE_PATH, Path)
        self.assertEqual(settings.TMP_PATH, Path("downloads/cache"))

    def test_initial_extensions_are_loaded_from_a_json_environment_value(self):
        environment = {
            "DISCORD_KEY": "discord-token",
            "LOG_CHANNEL": "1",
            "VIDEO_OUTPUT_CHANNEL": "2",
            "DOWNLOAD_CHANNEL": "4",
            "INITIAL_EXTENSIONS": '["yt_dl_bot.cogs.maincog","yt_dl_bot.cogs.systemcog"]',
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = Settings(_env_file=None)

        self.assertEqual(
            settings.INITIAL_EXTENSIONS,
            ("yt_dl_bot.cogs.maincog", "yt_dl_bot.cogs.systemcog"),
        )


if __name__ == "__main__":
    unittest.main()

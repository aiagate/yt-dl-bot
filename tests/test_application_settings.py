import importlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from yt_dl_bot.chatdatamodule import ChatDataModule
from yt_dl_bot.discord_bot_main import MyBot
from yt_dl_bot.setting import Settings
from yt_dl_bot.youtubemodule import YoutubeModule
from yt_dl_bot.ytdlpmodule import YtdlpModule


def settings_for(name):
    return Settings(
        _env_file=None,
        DISCORD_KEY=f"{name}-token",
        LOG_CHANNEL=1,
        VIDEO_OUTPUT_CHANNEL=2,
        HIGHLIGHT_OUTPUT_CHANNEL=3,
        DOWNLOAD_CHANNEL=4,
        HIGHLIGHT_CHANNEL=5,
        SAVE_PATH=f"/{name}/archive/",
        TMP_PATH=f"/{name}/cache/",
    )


class ApplicationSettingsTest(unittest.IsolatedAsyncioTestCase):
    async def test_bot_keeps_the_composition_root_settings_instance(self):
        settings = settings_for("first")
        services = SimpleNamespace(name="services")
        bot = MyBot(
            command_prefix="!",
            settings=settings,
            services=services,
        )
        self.addAsyncCleanup(bot.close)

        self.assertIs(bot.settings, settings)
        self.assertIs(bot.services, services)

    def test_distinct_settings_can_be_used_in_parallel(self):
        first = settings_for("first")
        second = settings_for("second")

        first_youtube = YoutubeModule(settings=first)
        second_ytdlp = YtdlpModule(settings=second)
        first_chat = ChatDataModule("video", settings=first)
        second_chat = ChatDataModule("video", settings=second)

        self.assertEqual(
            first_youtube.dependencies.tmp_path,
            Path("/first/cache"),
        )
        self.assertEqual(
            first_youtube.dependencies.save_path,
            Path("/first/archive"),
        )
        self.assertEqual(
            second_ytdlp.dependencies.tmp_path,
            Path("/second/cache"),
        )
        self.assertEqual(
            second_ytdlp.dependencies.save_path,
            Path("/second/archive"),
        )
        self.assertEqual(first_chat.image_path.parent, Path("/first/cache"))
        self.assertEqual(second_chat.image_path.parent, Path("/second/cache"))

    def test_property_compatibility_module_has_no_environment_side_effect(self):
        with patch.dict(os.environ, {}, clear=True):
            sys.modules.pop("yt_dl_bot.property", None)
            module = importlib.import_module("yt_dl_bot.property")

        self.assertEqual(
            module.INITIAL_EXTENSIONS,
            settings_for("test").INITIAL_EXTENSIONS,
        )
        self.assertFalse(hasattr(module, "DISCORD_KEY"))


if __name__ == "__main__":
    unittest.main()

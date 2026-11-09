import unittest
from pathlib import Path
from types import SimpleNamespace

from yt_dl_bot.discord_bot_main import DownloadBot
from yt_dl_bot.setting import Settings
from yt_dl_bot.youtube_downloader import YouTubeDownloader
from yt_dl_bot.yt_dlp_downloader import YtDlpDownloader


def settings_for(name):
    return Settings(
        _env_file=None,
        DISCORD_KEY=f"{name}-token",
        LOG_CHANNEL=1,
        VIDEO_OUTPUT_CHANNEL=2,
        DOWNLOAD_CHANNEL=4,
        SAVE_PATH=f"/{name}/archive/",
        TMP_PATH=f"/{name}/cache/",
    )


class ApplicationSettingsTest(unittest.IsolatedAsyncioTestCase):
    async def test_bot_keeps_the_composition_root_settings_instance(self):
        settings = settings_for("first")
        services = SimpleNamespace(name="services")
        bot = DownloadBot(
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

        first_youtube = YouTubeDownloader(settings=first)
        second_ytdlp = YtDlpDownloader(settings=second)

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


if __name__ == "__main__":
    unittest.main()

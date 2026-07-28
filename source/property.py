"""Backward-compatible application settings.

Existing modules import this file as ``property``. Values that vary by
deployment are loaded from environment variables by :class:`setting.Settings`.
"""

from setting import Settings


_settings = Settings()

INITIAL_EXTENSIONS = [
    'cogs.maincog',
    'cogs.systemcog',
    'cogs.youtubecog',
    'cogs.twitchcog',
]

LOG_CHANNEL = _settings.LOG_CHANNEL
VIDEO_OUTPUT_CHANNEL = _settings.VIDEO_OUTPUT_CHANNEL
HIGHLIGHT_OUTPUT_CHANNEL = _settings.HIGHLIGHT_OUTPUT_CHANNEL
DOWNLOAD_CHANNEL = _settings.DOWNLOAD_CHANNEL
HIGHLIGHT_CHANNEL = _settings.HIGHLIGHT_CHANNEL

SAVE_PATH = _settings.SAVE_PATH
GRAPH_SAVE_PATH = _settings.GRAPH_SAVE_PATH
TMP_PATH = _settings.TMP_PATH
LOG_PATH = _settings.LOG_PATH
COLLECTOR_LOG_PATH = _settings.COLLECTOR_LOG_PATH

DISCORD_KEY = _settings.DISCORD_KEY.get_secret_value()

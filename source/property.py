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
SEARCH_OUTPUT_CHANNEL = _settings.SEARCH_OUTPUT_CHANNEL
DOWNLOAD_CHANNEL = _settings.DOWNLOAD_CHANNEL
HIGHLIGHT_CHANNEL = _settings.HIGHLIGHT_CHANNEL
SEARCH_CHANNEL = _settings.SEARCH_CHANNEL

SAVE_PATH = _settings.SAVE_PATH
CHAT_DATA_SAVE_PATH = _settings.CHAT_DATA_SAVE_PATH
GRAPH_SAVE_PATH = _settings.GRAPH_SAVE_PATH
TMP_PATH = _settings.TMP_PATH
LOG_PATH = _settings.LOG_PATH
COLLECTOR_LOG_PATH = _settings.COLLECTOR_LOG_PATH
DOWNLOAD_DATA = 'databases/download.db'
DATABASE_PATH = 'databases/'

SQL_HOST = _settings.DB_HOSTNAME
SQL_USER = _settings.DB_USERNAME
SQL_PASSWD = _settings.DB_PASSWORD.get_secret_value()

SEEK_TIME_OFFSET = _settings.SEEK_TIME_OFFSET

DOWNLOAD_DATALIST = (
    ' ('
    'id CHAR(100) PRIMARY KEY,'
    'url TEXT,'
    'date TEXT,'
    'starttime TEXT'
    ')'
)
VIDEO_DATALIST = (
    ' ('
    'video_id CHAR(100) PRIMARY KEY,'
    'channel_id TEXT,'
    'title TEXT,'
    'description TEXT,'
    'duration DECIMAL,'
    'view_count INTEGER,'
    'is_live BOOLEAN'
    ')'
)
ARCHIVE_DATALIST = (
    '('
    'id CHAR(100) PRIMARY KEY,'
    'uploader TEXT,'
    'channel_id TEXT,'
    'channel_url TEXT,'
    'upload_date TEXT,'
    'start_time TEXT,'
    'endtime TEXT,'
    'title TEXT,'
    'description TEXT,'
    'webpage_url TEXT,'
    'is_live NUMERIC,'
    'width INTEGER,'
    'height INTEGER'
    ')'
)
CHAT_DATALIST = (
    '('
    'id CHAR(100) PRIMARY KEY,'
    'video_id CHAR(100),'
    'name TEXT,'
    'channel_id TEXT,'
    'type TEXT,'
    'message TEXT,'
    'datetime TEXT,'
    'elapsed_time INTEGER,'
    'amount_value REAL,'
    'amount_string TEXT,'
    'currency TEXT,'
    'is_verified NUMERIC,'
    'is_owner NUMERIC,'
    'is_sponsor NUMERIC,'
    'is_moderator NUMERIC,'
    'INDEX video_id_index (video_id)'
    ')'
)
CHAT_LITE = (
    '('
    'id CHAR(100) PRIMARY KEY,'
    'name TEXT,'
    'channel_id TEXT,'
    'type TEXT,'
    'message TEXT,'
    'datetime TEXT,'
    'timestamp INTEGER,'
    'amount_value REAL,'
    'amount_string TEXT,'
    'currency TEXT,'
    'is_verified NUMERIC,'
    'is_owner NUMERIC,'
    'is_sponsor NUMERIC,'
    'is_moderator NUMERIC'
    ')'
)

DISCORD_KEY = _settings.DISCORD_KEY.get_secret_value()
YOUTUBE_API_KEY = _settings.YOUTUBE_API_KEY.get_secret_value()

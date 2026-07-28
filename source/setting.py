#! .venv/bin/python
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

CURRENT_PATH = Path(__file__).resolve().parent


class Settings(BaseSettings):
    DISCORD_KEY: SecretStr
    YOUTUBE_API_KEY: SecretStr

    DB_HOSTNAME: str = 'database'
    DB_USERNAME: str
    DB_PASSWORD: SecretStr

    LOG_CHANNEL: int
    VIDEO_OUTPUT_CHANNEL: int
    HIGHLIGHT_OUTPUT_CHANNEL: int
    SEARCH_OUTPUT_CHANNEL: int
    DOWNLOAD_CHANNEL: int
    HIGHLIGHT_CHANNEL: int
    SEARCH_CHANNEL: int

    SAVE_PATH: str = 'downloads/'
    CHAT_DATA_SAVE_PATH: str = 'downloads/chatdata/'
    GRAPH_SAVE_PATH: str = 'downloads/graph/'
    TMP_PATH: str = 'downloads/cache/'
    LOG_PATH: str = 'logs/'
    COLLECTOR_LOG_PATH: str = 'logs/'

    SEEK_TIME_OFFSET: int = 15

    model_config = SettingsConfigDict(
        env_file=(
            f'{CURRENT_PATH.parent}/.env',
            f'{CURRENT_PATH}/.env',
            f'{CURRENT_PATH}/.env.local',
            f'{CURRENT_PATH}/.env.develop',
            f'{CURRENT_PATH}/.env.production',
        ),
        env_file_encoding='utf-8',
        extra='ignore',
    )

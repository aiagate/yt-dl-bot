#! .venv/bin/python
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

CURRENT_PATH = Path(__file__).resolve().parent

DEFAULT_INITIAL_EXTENSIONS = (
    'cogs.maincog',
    'cogs.systemcog',
    'cogs.youtubecog',
    'cogs.twitchcog',
)


class Settings(BaseSettings):
    INITIAL_EXTENSIONS: tuple[str, ...] = DEFAULT_INITIAL_EXTENSIONS

    DISCORD_KEY: SecretStr

    LOG_CHANNEL: int
    VIDEO_OUTPUT_CHANNEL: int
    HIGHLIGHT_OUTPUT_CHANNEL: int
    DOWNLOAD_CHANNEL: int
    HIGHLIGHT_CHANNEL: int

    SAVE_PATH: str = 'downloads/'
    GRAPH_SAVE_PATH: str = 'downloads/graph/'
    TMP_PATH: str = 'downloads/cache/'
    LOG_PATH: str = 'logs/'
    COLLECTOR_LOG_PATH: str = 'logs/'

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

"""Composition root for application services."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .video_download_service import TwitchDownloadService, VideoDownloadService
from .youtube_downloader import YouTubeDownloader
from .yt_dlp_downloader import YtDlpDownloader


class ApplicationSettings(Protocol):
    SAVE_PATH: Path
    TMP_PATH: Path


@dataclass(frozen=True)
class ApplicationServices:
    youtube_download: VideoDownloadService
    twitch_download: TwitchDownloadService

    @classmethod
    def from_settings(cls, settings: ApplicationSettings) -> "ApplicationServices":
        youtube = YouTubeDownloader(settings=settings)
        twitch = YtDlpDownloader(settings=settings)
        return cls(
            youtube_download=VideoDownloadService(youtube),
            twitch_download=TwitchDownloadService(twitch),
        )

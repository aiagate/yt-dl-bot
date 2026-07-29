"""Compatibility facade for the application service public API.

New code may import from the cohesive service modules directly. Existing callers
can continue importing every established name from this module.
"""

from .application_container import ApplicationServices, ApplicationSettings
from .application_results import DownloadResult, HighlightResult, split_highlight_text
from .video_download_service import (
    DOWNLOAD_ADAPTER_ERRORS,
    Cancellation,
    DownloadAdapter,
    TwitchDownloadService,
    TwitchStreamOffline,
    VideoDownloadService,
)
from .youtube_highlight_service import (
    CHAT_PROCESSING_ERRORS,
    YOUTUBE_METADATA_ERRORS,
    HighlightChat,
    HighlightYouTubeAdapter,
    MoveFile,
    YouTubeHighlightService,
    YoutubeHighlightService,
)

__all__ = [
    "CHAT_PROCESSING_ERRORS",
    "DOWNLOAD_ADAPTER_ERRORS",
    "YOUTUBE_METADATA_ERRORS",
    "ApplicationServices",
    "ApplicationSettings",
    "Cancellation",
    "DownloadAdapter",
    "DownloadResult",
    "HighlightChat",
    "HighlightResult",
    "HighlightYouTubeAdapter",
    "MoveFile",
    "TwitchDownloadService",
    "TwitchStreamOffline",
    "VideoDownloadService",
    "YouTubeHighlightService",
    "YoutubeHighlightService",
    "split_highlight_text",
]

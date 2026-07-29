"""YouTube download adapter."""

from .download_engine import (
    DownloadEngine,
    default_download_dependencies,
    youtube_download_policy,
)
from .setting import Settings
from .url_validation import extract_youtube_video_id


class YouTubeDownloader:
    def __init__(self, dependencies=None, retry_policy=None, settings=None):
        if dependencies is None:
            dependencies = default_download_dependencies(
                settings or Settings(),
            )
        self.dependencies = dependencies
        self.retry_policy = retry_policy or youtube_download_policy().retry_policy
        self.engine = DownloadEngine(
            dependencies,
            youtube_download_policy(self.retry_policy),
        )

    def check_availability(self, url):
        return self.engine.check_availability(url, info_loader=self.get_info)

    def download_video(self, url):
        return self.engine.download_video(url, info_loader=self.get_info)

    def download_video_cancellable(self, url, cancellation_token):
        return self.engine.download_video(
            url,
            info_loader=self.get_info,
            cancellation_token=cancellation_token,
        )

    def get_info(self, url):
        return self.engine.get_info(url)

    def get_video_id(self, url):
        return extract_youtube_video_id(url)

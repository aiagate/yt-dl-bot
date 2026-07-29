"""Generic yt-dlp download adapter."""

from .download_engine import (
    DownloadEngine,
    default_download_dependencies,
    generic_download_policy,
)
from .setting import Settings


class YtDlpDownloader:
    def __init__(self, dependencies=None, settings=None):
        if dependencies is None:
            dependencies = default_download_dependencies(
                settings or Settings(),
            )
        self.dependencies = dependencies
        self.engine = DownloadEngine(
            dependencies,
            generic_download_policy(),
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

"""Backward-compatible YouTube download facade."""

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

    def live_timer(self, info):
        return self.engine.live_timer(info)

    def build_options(self, outpath):
        return self.engine.build_options(outpath)

    def get_video_id(self, url):
        return extract_youtube_video_id(url)

    # Compatibility wrappers for callers using the original public API.
    def data_check(self, url):
        return self.check_availability(url)

    def ops(self, info, outpath):
        del info
        return self.build_options(outpath)

    def get_videoid(self, url):
        return self.get_video_id(url)


# Compatibility alias. New code should use YouTubeDownloader.
YoutubeModule = YouTubeDownloader

"""Backward-compatible YouTube download facade."""

from download_engine import (
    DownloadEngine,
    default_download_dependencies,
    youtube_download_policy,
)
from setting import Settings
from url_validation import extract_youtube_video_id


class YoutubeModule:
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

    def data_check(self, url):
        return self.engine.data_check(url, info_loader=self.get_info)

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

    def ops(self, info, outpath):
        return self.engine.build_options(outpath)

    def get_videoid(self, url):
        return extract_youtube_video_id(url)

"""Backward-compatible generic yt-dlp download facade."""

from download_engine import (
    DownloadEngine,
    default_download_dependencies,
    generic_download_policy,
)
from setting import Settings
from url_validation import extract_youtube_video_id


class YtdlpModule:
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

    def data_check(self, url):
        return self.engine.data_check(url, info_loader=self.get_info)

    def download_video(self, url):
        return self.engine.download_video(url, info_loader=self.get_info)

    def get_info(self, url):
        return self.engine.get_info(url)

    def live_timer(self, info):
        return self.engine.live_timer(info)

    def ops(self, outpath):
        return self.engine.build_options(outpath)

    def get_videoid(self, url):
        return extract_youtube_video_id(url)

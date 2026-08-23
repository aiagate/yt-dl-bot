"""YouTube download adapter."""

from .download_adapter import EngineDownloadAdapter
from .download_engine import (
    DownloadSettings,
    default_download_dependencies,
    youtube_download_policy,
)
from .download_primitives import DownloadDependencies, RetryPolicy
from .setting import Settings
from .url_validation import extract_youtube_video_id


class YouTubeDownloader(EngineDownloadAdapter):
    def __init__(
        self,
        dependencies: DownloadDependencies | None = None,
        retry_policy: RetryPolicy | None = None,
        settings: DownloadSettings | None = None,
    ) -> None:
        if dependencies is None:
            dependencies = default_download_dependencies(
                settings or Settings(),
            )
        self.retry_policy = retry_policy or youtube_download_policy().retry_policy
        super().__init__(
            dependencies,
            youtube_download_policy(self.retry_policy),
        )

    def get_video_id(self, url: str) -> str:
        return extract_youtube_video_id(url)

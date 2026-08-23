"""Generic yt-dlp download adapter."""

from .download_adapter import EngineDownloadAdapter
from .download_engine import (
    DownloadSettings,
    default_download_dependencies,
    generic_download_policy,
)
from .download_primitives import DownloadDependencies
from .setting import Settings


class YtDlpDownloader(EngineDownloadAdapter):
    def __init__(
        self,
        dependencies: DownloadDependencies | None = None,
        settings: DownloadSettings | None = None,
    ) -> None:
        if dependencies is None:
            dependencies = default_download_dependencies(
                settings or Settings(),
            )
        super().__init__(
            dependencies,
            generic_download_policy(),
        )

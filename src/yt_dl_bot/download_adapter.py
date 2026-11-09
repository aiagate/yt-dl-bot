"""Common adapter API for site-specific :class:`DownloadEngine` policies."""

from .download_engine import Cancellation, DownloadEngine, DownloadOutcome, DownloadPolicy
from .download_primitives import DownloadDependencies


class EngineDownloadAdapter:
    """Expose a stable downloader API backed by one engine and one policy."""

    def __init__(self, dependencies: DownloadDependencies, policy: DownloadPolicy) -> None:
        self.dependencies = dependencies
        self.engine = DownloadEngine(dependencies, policy)

    def check_availability(self, url: str) -> str:
        return self.engine.check_availability(url, info_loader=self.get_info)

    def download_video(
        self,
        url: str,
        cancellation_token: Cancellation | None = None,
    ) -> DownloadOutcome:
        return self.engine.download_video(
            url,
            info_loader=self.get_info,
            cancellation_token=cancellation_token,
        )

    def get_info(self, url: str) -> dict[str, object]:
        return self.engine.get_info(url)

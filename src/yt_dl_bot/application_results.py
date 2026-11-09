"""Application result models shared by use cases and delivery adapters."""

from dataclasses import dataclass
from pathlib import Path

from .download_engine import DownloadOutcome


@dataclass(frozen=True)
class DownloadResult:
    video_id: str
    title: str
    source_url: str
    video_file: Path
    metadata_files: tuple[Path, ...]
    thumbnail_files: tuple[Path, ...]

    @classmethod
    def from_outcome(cls, outcome: object) -> "DownloadResult":
        if not isinstance(outcome, DownloadOutcome):
            raise TypeError(
                "download adapter must return DownloadOutcome",
            )
        return cls(
            video_id=outcome.video_id,
            title=outcome.title,
            source_url=outcome.source_url,
            video_file=outcome.artifacts.video,
            metadata_files=outcome.artifacts.metadata,
            thumbnail_files=outcome.artifacts.thumbnails,
        )

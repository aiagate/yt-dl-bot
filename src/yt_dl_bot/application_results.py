"""Application result models and presentation-ready highlight formatting."""

import datetime
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .download_engine import DownloadOutcome
from .highlight import Highlight


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


@dataclass(frozen=True)
class HighlightResult:
    title: str
    channel_name: str
    thumbnail_url: str
    graph_image: Path
    highlight_fields: tuple[str, ...]


def split_highlight_text(
    highlights: Iterable[Highlight],
    max_length: int = 1024,
) -> tuple[str, ...]:
    """Format highlight links into fields within Discord's size limit."""
    if max_length < 2:
        raise ValueError("max_length must be at least 2")

    field_limit = max_length - 1
    fields: list[str] = []
    current = ""
    for highlight in highlights:
        line = f"{datetime.timedelta(seconds=highlight.seconds)}\t{highlight.url}\n"
        line = line[:field_limit]
        if current and len(current + line) > field_limit:
            fields.append(current)
            current = ""
        current += line
    if current:
        fields.append(current)
    return tuple(fields) or ("does not get highlight"[:field_limit],)

"""External side-effect boundary for download services."""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Protocol


class YoutubeDLFactory(Protocol):
    def __call__(self, options: dict | None = None): ...


@dataclass(frozen=True)
class DownloadDependencies:
    """Injectable operations used by the legacy download modules."""

    ydl_factory: YoutubeDLFactory
    now: Callable[[], datetime]
    sleep: Callable[[float], None]
    path_exists: Callable[[str], bool]
    make_directory: Callable[[str], None]
    move: Callable[[str, str], object]
    tmp_path: str
    save_path: str

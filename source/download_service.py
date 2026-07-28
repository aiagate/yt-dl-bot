"""External side-effect boundary for download services."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Protocol

from external_error_adapter import youtube_scheduled_delay


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


class RetryStatus(Enum):
    RETRYABLE = 'retryable'
    PERMANENT_FAILURE = 'permanent_failure'


@dataclass(frozen=True)
class RetryDecision:
    status: RetryStatus
    wait_seconds: float = 0


class DownloadWaitError(Exception):
    """Base exception for failures while waiting for a scheduled download."""

    def __init__(self, message, *, original_error, attempts, waited_seconds):
        super().__init__(message)
        self.original_error = original_error
        self.attempts = attempts
        self.waited_seconds = waited_seconds


class PermanentDownloadError(DownloadWaitError):
    """The failure is not a recognized scheduled-live condition."""


class DownloadRetryLimitExceeded(DownloadWaitError):
    """A scheduled download exceeded its configured retry budget."""


@dataclass(frozen=True)
class RetryPolicy:
    """Bound retry policy for YouTube scheduled-live metadata checks."""

    max_attempts: int = 10
    max_wait_seconds: float = 6 * 60 * 60

    def __post_init__(self):
        if self.max_attempts < 1:
            raise ValueError('max_attempts must be at least 1')
        if self.max_wait_seconds < 0:
            raise ValueError('max_wait_seconds must not be negative')

    def decide(self, error) -> RetryDecision:
        wait_seconds = youtube_scheduled_delay(error)
        if wait_seconds is None:
            return RetryDecision(RetryStatus.PERMANENT_FAILURE)
        return RetryDecision(RetryStatus.RETRYABLE, wait_seconds)

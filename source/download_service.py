"""External side-effect boundary for download services."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re
from typing import Callable, Protocol

import yt_dlp


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
        if not isinstance(error, yt_dlp.utils.DownloadError):
            return RetryDecision(RetryStatus.PERMANENT_FAILURE)

        message = str(error.args)
        if (
            'This live event will begin' not in message
            and 'Premiere' not in message
        ):
            return RetryDecision(RetryStatus.PERMANENT_FAILURE)

        if 'few' in message or 'shortly' in message:
            return RetryDecision(RetryStatus.RETRYABLE, 15)

        match = re.search(
            r'(\d+)\s+(days?|hours?|minutes?|seconds?)',
            message,
        )
        if match is None:
            return RetryDecision(RetryStatus.PERMANENT_FAILURE)

        value = max(int(match.group(1)) - 0.5, 0)
        unit = match.group(2)
        multiplier = {
            'day': 86400,
            'days': 86400,
            'hour': 3600,
            'hours': 3600,
            'minute': 60,
            'minutes': 60,
            'second': 1,
            'seconds': 1,
        }[unit]
        return RetryDecision(RetryStatus.RETRYABLE, value * multiplier)

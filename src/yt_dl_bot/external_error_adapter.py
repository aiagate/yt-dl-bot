"""Interpret unstable external-library error representations.

All message matching lives in this module so the rest of the application can
depend on a small, structured result instead of yt-dlp's human-readable text.
"""

import re
from dataclasses import dataclass
from enum import Enum

import yt_dlp


class ExternalErrorKind(Enum):
    YOUTUBE_SCHEDULED = "youtube_scheduled"
    TWITCH_OFFLINE = "twitch_offline"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ExternalError:
    kind: ExternalErrorKind
    detail: str
    reason: str
    retryable: bool = False
    wait_seconds: float | None = None


_YOUTUBE_SCHEDULED = re.compile(
    r"(?:This live event will begin|Premieres?)"
    r"(?:\s+in)?\s+"
    r"(?P<wait>"
    r"(?:a\s+)?(?:few|shortly)"
    r"|(?:\d+)\s+(?:days?|hours?|minutes?|seconds?)"
    r")",
)
_WAIT_DURATION = re.compile(
    r"(?P<value>\d+)\s+"
    r"(?P<unit>days?|hours?|minutes?|seconds?)",
)
_TWITCH_OFFLINE = re.compile(r"\bThe channel is not currently live\b")


def error_detail(error):
    exc_info = getattr(error, "exc_info", None)
    if isinstance(exc_info, tuple) and len(exc_info) > 1:
        return str(exc_info[1])
    return str(error)


def parse_external_error(error):
    """Return a stable classification and a loggable reason for *error*."""
    detail = error_detail(error)

    if isinstance(error, yt_dlp.utils.DownloadError):
        scheduled = _YOUTUBE_SCHEDULED.search(detail)
        if scheduled is not None:
            wait_text = scheduled.group("wait")
            wait_seconds: float
            if "few" in wait_text or "shortly" in wait_text:
                wait_seconds = 15
            else:
                duration = _WAIT_DURATION.fullmatch(wait_text)
                if duration is None:  # Defensive: kept separate from matching.
                    return ExternalError(
                        ExternalErrorKind.UNKNOWN,
                        detail,
                        "youtube_scheduled_wait_unparseable",
                    )
                value = max(int(duration.group("value")) - 0.5, 0.0)
                multiplier = {
                    "day": 86400,
                    "days": 86400,
                    "hour": 3600,
                    "hours": 3600,
                    "minute": 60,
                    "minutes": 60,
                    "second": 1,
                    "seconds": 1,
                }[duration.group("unit")]
                wait_seconds = value * multiplier
            return ExternalError(
                ExternalErrorKind.YOUTUBE_SCHEDULED,
                detail,
                "matched_youtube_scheduled_message",
                retryable=True,
                wait_seconds=wait_seconds,
            )

    if _TWITCH_OFFLINE.search(detail) is not None:
        return ExternalError(
            ExternalErrorKind.TWITCH_OFFLINE,
            detail,
            "matched_twitch_offline_message",
        )

    return ExternalError(
        ExternalErrorKind.UNKNOWN,
        detail,
        "no_known_external_error_pattern",
    )


def youtube_scheduled_notice(error):
    parsed = parse_external_error(error)
    if parsed.kind is not ExternalErrorKind.YOUTUBE_SCHEDULED:
        return None
    detail = parsed.detail
    if "This live event will begin in" in detail:
        wait = detail.replace("This live event will begin in ", "")
        return f"{detail}. Will be downloaded in {wait}"
    if "Premieres" in detail:
        wait = detail.replace("Premieres ", "")
        return f"{detail}. Will be downloaded in {wait}"
    return None


def youtube_scheduled_delay(error):
    parsed = parse_external_error(error)
    if not parsed.retryable:
        return None
    return parsed.wait_seconds


def is_twitch_offline(error):
    return parse_external_error(error).kind is ExternalErrorKind.TWITCH_OFFLINE

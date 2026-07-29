"""Discord-independent helpers for formatting error reports."""

import re
import traceback
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DISCORD_FIELD_VALUE_LIMIT = 1024
# Five maximum-sized values plus their field names remain below Discord's
# 6,000-character aggregate limit for an embed.
DISCORD_FIELDS_PER_EMBED = 5
EMPTY_TRACEBACK_MESSAGE = "No traceback available."
REDACTED = "<redacted>"
LOCAL_PATH = "<local-path>"

_SENSITIVE_NAMES = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "client_secret",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "passwd",
        "password",
        "refresh_token",
        "secret",
        "session",
        "session_id",
        "sessionid",
        "token",
    }
)
_URL_PATTERN = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)
_HEADER_PATTERN = re.compile(
    r"(?im)^(\s*(?:authorization|proxy-authorization|cookie|set-cookie)\s*:\s*).*$"
)
_KEY_VALUE_PATTERN = re.compile(
    r"""(?ix)
    (?P<prefix>
        \b(?:access_token|api_key|apikey|auth|authorization|client_secret|cookie|
        cookies|credential|credentials|passwd|password|refresh_token|secret|
        session|session_id|sessionid|token)\b
        \s*[:=]\s*
    )
    (?P<quote>["']?)
    (?P<value>[^\s&,;}\]"']+)
    (?P=quote)
    """
)
_POSIX_PATH_PATTERN = re.compile(r"(?<![\w:/])/(?:[^/\s\"'<>]+/)+[^/\s\"'<>]*")
_WINDOWS_PATH_PATTERN = re.compile(
    r"(?i)(?<![\w])(?:[a-z]:\\|\\\\[^\\\s\"'<>]+\\[^\\\s\"'<>]+\\)"
    r"(?:[^\\\s\"'<>]+\\)*[^\\\s\"'<>]*"
)


def format_exception_traceback(error: BaseException) -> str:
    """Return the complete traceback for an exception."""
    return "".join(
        traceback.format_exception(type(error), error, error.__traceback__),
    )


def _redact_url(match: re.Match[str]) -> str:
    raw_url = match.group(0)
    trailing = ""
    while raw_url and raw_url[-1] in ".,);]>":
        trailing = raw_url[-1] + trailing
        raw_url = raw_url[:-1]

    try:
        parts = urlsplit(raw_url)
        hostname = parts.hostname or ""
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        if parts.port is not None:
            hostname = f"{hostname}:{parts.port}"
    except ValueError:
        return f"<redacted-url>{trailing}"
    if parts.username is not None or parts.password is not None:
        hostname = f"{REDACTED}@{hostname}"

    query = urlencode(
        [
            (name, REDACTED if name.casefold() in _SENSITIVE_NAMES else value)
            for name, value in parse_qsl(parts.query, keep_blank_values=True)
        ],
        doseq=True,
    )
    return urlunsplit((parts.scheme, hostname, parts.path, query, parts.fragment)) + trailing


def _redact_posix_path(match: re.Match[str]) -> str:
    name = PurePosixPath(match.group(0)).name
    return f"{LOCAL_PATH}/{name}" if name else LOCAL_PATH


def _redact_windows_path(match: re.Match[str]) -> str:
    name = PureWindowsPath(match.group(0)).name
    return f"{LOCAL_PATH}/{name}" if name else LOCAL_PATH


def sanitize_discord_error_report(error_log: str) -> str:
    """Redact common credentials and local paths before Discord transmission.

    This is deliberately deterministic and conservative. It covers structured,
    commonly leaked values; it is not a guarantee that arbitrary secret text
    embedded in an exception message will be recognized.
    """
    sanitized = _URL_PATTERN.sub(_redact_url, error_log)
    sanitized = _HEADER_PATTERN.sub(rf"\1{REDACTED}", sanitized)
    sanitized = _KEY_VALUE_PATTERN.sub(rf"\g<prefix>{REDACTED}", sanitized)
    sanitized = _WINDOWS_PATH_PATTERN.sub(_redact_windows_path, sanitized)
    return _POSIX_PATH_PATTERN.sub(_redact_posix_path, sanitized)


def split_traceback_for_embeds(
    error_log: str,
    *,
    field_value_limit: int = DISCORD_FIELD_VALUE_LIMIT,
    fields_per_embed: int = DISCORD_FIELDS_PER_EMBED,
) -> tuple[tuple[str, ...], ...]:
    """Split a traceback into embed-sized batches without losing text."""
    if field_value_limit <= 0:
        raise ValueError("field_value_limit must be positive")
    if fields_per_embed <= 0:
        raise ValueError("fields_per_embed must be positive")

    text = error_log or EMPTY_TRACEBACK_MESSAGE
    chunks = tuple(
        text[index : index + field_value_limit] for index in range(0, len(text), field_value_limit)
    )
    return tuple(
        chunks[index : index + fields_per_embed]
        for index in range(0, len(chunks), fields_per_embed)
    )

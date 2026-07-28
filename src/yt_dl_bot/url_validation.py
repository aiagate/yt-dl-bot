"""Pure URL validation for user-supplied video links."""

from dataclasses import dataclass
import re
from urllib.parse import parse_qs, urlsplit


YOUTUBE_HOSTS = frozenset({
    'youtube.com',
    'www.youtube.com',
    'm.youtube.com',
    'music.youtube.com',
    'youtu.be',
})
TWITCH_HOSTS = frozenset({
    'twitch.tv',
    'www.twitch.tv',
    'm.twitch.tv',
    'clips.twitch.tv',
})

SERVICE_HOSTS = {
    'youtube': YOUTUBE_HOSTS,
    'twitch': TWITCH_HOSTS,
}

_VIDEO_ID = re.compile(r'^[A-Za-z0-9_-]{1,128}$')


@dataclass(frozen=True)
class YoutubeVideoReference:
    video_id: str
    canonical_url: str


def identify_service(value: str) -> str | None:
    """Return the supported video service for a safe HTTP(S) URL."""
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except (AttributeError, TypeError, ValueError):
        return None

    if (
        parsed.scheme.lower() not in {'http', 'https'}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
    ):
        return None

    hostname = parsed.hostname.lower().rstrip('.')
    for service, hosts in SERVICE_HOSTS.items():
        if hostname in hosts:
            return service
    return None


def validate_service_url(value: str, service: str) -> str:
    """Return a stripped URL when it belongs to ``service`` or raise."""
    url = value.strip() if isinstance(value, str) else value
    if service not in SERVICE_HOSTS:
        raise ValueError(f'Unsupported service: {service}')
    if identify_service(url) != service:
        raise ValueError(f'Invalid {service} URL')
    return url


def parse_youtube_video_url(value: str) -> YoutubeVideoReference:
    """Parse a supported YouTube video URL without network access.

    This is intended for work that needs an ID before yt-dlp extraction.
    Once extraction succeeds, callers should treat yt-dlp's ``info['id']`` as
    authoritative.
    """
    url = validate_service_url(value, 'youtube')
    parsed = urlsplit(url)
    hostname = parsed.hostname.lower().rstrip('.')

    if hostname == 'youtu.be':
        segments = parsed.path.split('/')
        video_id = (
            segments[1]
            if len(segments) == 2 and segments[0] == ''
            else None
        )
    elif parsed.path == '/watch':
        video_ids = parse_qs(
            parsed.query,
            keep_blank_values=True,
        ).get('v', [])
        video_id = video_ids[0] if len(video_ids) == 1 else None
    else:
        segments = parsed.path.split('/')
        video_id = (
            segments[2]
            if (
                len(segments) == 3
                and segments[0] == ''
                and segments[1] in {'shorts', 'live', 'embed'}
            )
            else None
        )

    if video_id is None or _VIDEO_ID.fullmatch(video_id) is None:
        raise ValueError('Invalid YouTube video URL')

    return YoutubeVideoReference(
        video_id=video_id,
        canonical_url=f'https://www.youtube.com/watch?v={video_id}',
    )


def extract_youtube_video_id(value: str) -> str:
    return parse_youtube_video_url(value).video_id

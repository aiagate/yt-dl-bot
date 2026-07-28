"""Pure URL validation for user-supplied video links."""

from urllib.parse import urlsplit


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

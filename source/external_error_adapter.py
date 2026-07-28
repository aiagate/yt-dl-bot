"""Interpret unstable external-library error representations."""

import re

import yt_dlp


def error_detail(error):
    exc_info = getattr(error, 'exc_info', None)
    if isinstance(exc_info, tuple) and len(exc_info) > 1:
        return str(exc_info[1])
    return str(error)


def youtube_scheduled_notice(error):
    if not isinstance(error, yt_dlp.utils.DownloadError):
        return None
    detail = error_detail(error)
    if 'This live event will begin in' in detail:
        wait = detail.replace('This live event will begin in ', '')
        return f'{detail}. Will be downloaded in {wait}'
    if 'Premieres' in detail:
        wait = detail.replace('Premieres ', '')
        return f'{detail}. Will be downloaded in {wait}'
    return None


def youtube_scheduled_delay(error):
    if not isinstance(error, yt_dlp.utils.DownloadError):
        return None

    message = error_detail(error)
    if (
        'This live event will begin' not in message
        and 'Premiere' not in message
    ):
        return None
    if 'few' in message or 'shortly' in message:
        return 15

    match = re.search(
        r'(\d+)\s+(days?|hours?|minutes?|seconds?)',
        message,
    )
    if match is None:
        return None

    value = max(int(match.group(1)) - 0.5, 0)
    multiplier = {
        'day': 86400,
        'days': 86400,
        'hour': 3600,
        'hours': 3600,
        'minute': 60,
        'minutes': 60,
        'second': 1,
        'seconds': 1,
    }[match.group(2)]
    return value * multiplier


def is_twitch_offline(error):
    return 'The channel is not currently live' in error_detail(error)

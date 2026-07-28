"""Pure routing decisions for Discord messages."""

from dataclasses import dataclass
from enum import Enum

from .url_validation import identify_service


class MessageAction(Enum):
    IGNORE = 'ignore'
    COMMAND = 'command'
    YOUTUBE_DOWNLOAD = 'youtube download'
    YOUTUBE_HIGHLIGHT = 'youtube highlight'
    TWITCH_DOWNLOAD = 'twitch download'

    @property
    def command_name(self):
        if self in {self.IGNORE, self.COMMAND}:
            return None
        return self.value


@dataclass(frozen=True)
class MessageRoute:
    action: MessageAction
    url: str | None = None


@dataclass(frozen=True)
class MessageRouter:
    command_prefix: str | tuple[str, ...]
    download_channel: int
    highlight_channel: int

    def route(self, *, author_is_bot, content, channel_id):
        if author_is_bot or not isinstance(content, str):
            return MessageRoute(MessageAction.IGNORE)

        prefixes = (
            (self.command_prefix,)
            if isinstance(self.command_prefix, str)
            else tuple(self.command_prefix)
        )
        if any(prefix and content.startswith(prefix) for prefix in prefixes):
            return MessageRoute(MessageAction.COMMAND)

        url = content.strip()
        service = identify_service(url)
        if service == 'youtube':
            if channel_id == self.highlight_channel:
                return MessageRoute(MessageAction.YOUTUBE_HIGHLIGHT, url)
            if channel_id == self.download_channel:
                return MessageRoute(MessageAction.YOUTUBE_DOWNLOAD, url)
        if service == 'twitch' and channel_id == self.download_channel:
            return MessageRoute(MessageAction.TWITCH_DOWNLOAD, url)
        return MessageRoute(MessageAction.IGNORE)

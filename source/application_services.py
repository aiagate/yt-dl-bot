"""Discord-independent application services."""

import datetime
import os
import shutil
from dataclasses import dataclass

from application_errors import (
    ArtifactStorageError,
    HighlightCreationError,
    VideoCheckError,
    VideoDownloadError,
)
from chatdatamodule import ChatDataModule
from external_error_adapter import error_detail, is_twitch_offline
from youtubemodule import YoutubeModule
from ytdlpmodule import YtdlpModule


@dataclass(frozen=True)
class DownloadResult:
    url: str
    info: dict


@dataclass(frozen=True)
class HighlightResult:
    title: str
    channel_name: str
    thumbnail_url: str
    graph_image: str
    highlight_fields: tuple[str, ...]


class TwitchStreamOffline(Exception):
    """The requested Twitch channel is not currently live."""


def split_highlight_text(highlights, max_length=1024):
    """Format highlight links into fields within Discord's size limit."""
    if max_length < 2:
        raise ValueError('max_length must be at least 2')

    field_limit = max_length - 1
    fields = []
    current = ''
    for seconds, url in highlights:
        line = f'{datetime.timedelta(seconds=seconds)}\t{url}\n'
        line = line[:field_limit]
        if current and len(current + line) > field_limit:
            fields.append(current)
            current = ''
        current += line
    if current:
        fields.append(current)
    return tuple(fields) or ('does not get highlight'[:field_limit],)


class VideoDownloadService:
    def __init__(self, downloader):
        self.downloader = downloader

    def check(self, url):
        try:
            return self.downloader.data_check(url=url, ydl_ops={})
        except Exception as error:
            raise VideoCheckError(
                f'Unable to check video: {error_detail(error)}',
                original_error=error,
            ) from error

    def download(self, url):
        try:
            info = self.downloader.download_video(url=url)
        except Exception as error:
            raise VideoDownloadError(
                f'Unable to download video: {error_detail(error)}',
                original_error=error,
            ) from error
        return DownloadResult(url=url, info=info)


class TwitchDownloadService(VideoDownloadService):
    def check(self, url):
        try:
            return self.downloader.data_check(url=url, ydl_ops={})
        except Exception as error:
            if is_twitch_offline(error):
                raise TwitchStreamOffline(error_detail(error)) from error
            raise VideoCheckError(
                f'Unable to check Twitch stream: {error_detail(error)}',
                original_error=error,
            ) from error


class YoutubeHighlightService:
    def __init__(
        self,
        settings,
        youtube,
        chat_factory=None,
        path_exists=os.path.exists,
        make_directory=os.mkdir,
        move=shutil.move,
    ):
        self.settings = settings
        self.youtube = youtube
        self.chat_factory = chat_factory or (
            lambda video_id: ChatDataModule(video_id, settings=settings)
        )
        self.path_exists = path_exists
        self.make_directory = make_directory
        self.move = move

    def create(self, url):
        try:
            video_id = self.youtube.get_videoid(url=url)
            video_info = self.youtube.get_info(url=url)
            chat = self.chat_factory(video_id)
            highlights = chat.get_highlight()
            title = video_info.get('fulltitle', video_info['title'])
        except Exception as error:
            raise HighlightCreationError(
                f'Unable to create highlights: {error_detail(error)}',
                original_error=error,
            ) from error
        return HighlightResult(
            title=title,
            channel_name=video_info['channel'],
            thumbnail_url=video_info['thumbnail'],
            graph_image=chat.image_path,
            highlight_fields=split_highlight_text(highlights),
        )

    def archive_graph(self, graph_image):
        try:
            output_path = self.settings.GRAPH_SAVE_PATH
            if not self.path_exists(output_path):
                self.make_directory(output_path)
            self.move(graph_image, output_path)
        except (OSError, shutil.Error) as error:
            raise ArtifactStorageError(
                f'Unable to archive highlight graph: {error}',
                original_error=error,
            ) from error


@dataclass(frozen=True)
class ApplicationServices:
    youtube_download: VideoDownloadService
    youtube_highlight: YoutubeHighlightService
    twitch_download: TwitchDownloadService

    @classmethod
    def from_settings(cls, settings):
        youtube = YoutubeModule(settings=settings)
        twitch = YtdlpModule(settings=settings)
        return cls(
            youtube_download=VideoDownloadService(youtube),
            youtube_highlight=YoutubeHighlightService(settings, youtube),
            twitch_download=TwitchDownloadService(twitch),
        )

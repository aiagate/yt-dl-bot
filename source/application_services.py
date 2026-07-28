"""Discord-independent application services."""

import datetime
import shutil
from dataclasses import dataclass
from pathlib import Path

import yt_dlp
from pytchat import exceptions as pytchat_exceptions

from application_errors import (
    ArtifactStorageError,
    HighlightCreationError,
    VideoCheckError,
    VideoDownloadError,
)
from artifact_discovery import ArtifactDiscoveryError
from chatdatamodule import ChatDataModule
from download_engine import DownloadOutcome
from download_service import DownloadWaitError
from external_error_adapter import error_detail, is_twitch_offline
from youtubemodule import YoutubeModule
from ytdlpmodule import YtdlpModule


DOWNLOAD_ADAPTER_ERRORS = (
    yt_dlp.utils.DownloadError,
    yt_dlp.utils.ExtractorError,
    DownloadWaitError,
    ArtifactDiscoveryError,
    OSError,
    shutil.Error,
)

YOUTUBE_METADATA_ERRORS = (
    yt_dlp.utils.DownloadError,
    yt_dlp.utils.ExtractorError,
    ValueError,
)

CHAT_PROCESSING_ERRORS = (
    pytchat_exceptions.ChatParseException,
    pytchat_exceptions.ResponseContextError,
    pytchat_exceptions.NoContents,
    pytchat_exceptions.NoContinuation,
    pytchat_exceptions.IllegalFunctionCall,
    pytchat_exceptions.InvalidVideoIdException,
    pytchat_exceptions.UnknownConnectionError,
    pytchat_exceptions.RetryExceedMaxCount,
    pytchat_exceptions.ChatDataFinished,
    pytchat_exceptions.ReceivedUnknownContinuation,
    pytchat_exceptions.FailedExtractContinuation,
    pytchat_exceptions.VideoInfoParseError,
    pytchat_exceptions.PatternUnmatchError,
    OSError,
)


@dataclass(frozen=True)
class DownloadResult:
    video_id: str
    title: str
    source_url: str
    video_file: Path
    metadata_files: tuple[Path, ...]
    thumbnail_files: tuple[Path, ...]

    @classmethod
    def from_outcome(cls, outcome):
        if not isinstance(outcome, DownloadOutcome):
            raise TypeError(
                'download adapter must return DownloadOutcome',
            )
        return cls(
            video_id=outcome.video_id,
            title=outcome.title,
            source_url=outcome.source_url,
            video_file=outcome.artifacts.video,
            metadata_files=outcome.artifacts.metadata,
            thumbnail_files=outcome.artifacts.thumbnails,
        )


@dataclass(frozen=True)
class HighlightResult:
    title: str
    channel_name: str
    thumbnail_url: str
    graph_image: Path
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
            return self.downloader.data_check(url=url)
        except DOWNLOAD_ADAPTER_ERRORS as error:
            raise VideoCheckError(
                f'Unable to check video: {error_detail(error)}',
                original_error=error,
            ) from error

    def download(self, url, cancellation_token=None):
        try:
            if cancellation_token is None:
                outcome = self.downloader.download_video(url=url)
            else:
                outcome = self.downloader.download_video_cancellable(
                    url=url,
                    cancellation_token=cancellation_token,
                )
        except DOWNLOAD_ADAPTER_ERRORS as error:
            raise VideoDownloadError(
                f'Unable to download video: {error_detail(error)}',
                original_error=error,
            ) from error
        return DownloadResult.from_outcome(outcome)


class TwitchDownloadService(VideoDownloadService):
    def check(self, url):
        try:
            return self.downloader.data_check(url=url)
        except DOWNLOAD_ADAPTER_ERRORS as error:
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
        path_exists=Path.exists,
        make_directory=Path.mkdir,
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
        except YOUTUBE_METADATA_ERRORS as error:
            raise HighlightCreationError(
                f'Unable to create highlights: {error_detail(error)}',
                original_error=error,
            ) from error

        chat = self.chat_factory(video_id)
        try:
            highlights = chat.get_highlight()
        except CHAT_PROCESSING_ERRORS as error:
            raise HighlightCreationError(
                f'Unable to create highlights: {error_detail(error)}',
                original_error=error,
            ) from error

        try:
            title = video_info.get('fulltitle') or video_info['title']
            channel_name = video_info['channel']
            thumbnail_url = video_info['thumbnail']
        except (KeyError, TypeError) as error:
            # yt-dlp metadata is external input. Treat a malformed schema as an
            # adapter failure, while leaving unrelated programming errors free
            # to propagate.
            raise HighlightCreationError(
                f'Unable to create highlights: {error_detail(error)}',
                original_error=error,
            ) from error
        return HighlightResult(
            title=title,
            channel_name=channel_name,
            thumbnail_url=thumbnail_url,
            graph_image=Path(chat.image_path),
            highlight_fields=split_highlight_text(highlights),
        )

    def archive_graph(self, graph_image):
        try:
            output_path = Path(self.settings.GRAPH_SAVE_PATH)
            if not self.path_exists(output_path):
                self.make_directory(
                    output_path,
                    parents=True,
                    exist_ok=True,
                )
            self.move(Path(graph_image), output_path)
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

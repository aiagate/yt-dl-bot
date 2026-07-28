"""Shared yt-dlp download engine with explicit site policies."""

import datetime
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

from artifact_discovery import DownloadedArtifacts, discover_download_artifacts
from download_service import (
    DownloadDependencies,
    DownloadRetryLimitExceeded,
    PermanentDownloadError,
    RetryPolicy,
    RetryStatus,
)
from external_error_adapter import (
    youtube_scheduled_delay,
    youtube_scheduled_notice,
)


@dataclass(frozen=True)
class DownloadPolicy:
    retry_policy: RetryPolicy | None
    scheduled_notice: bool
    require_metadata: bool
    require_thumbnail: bool
    live_from_start: bool
    use_cookie_file: bool
    cookie_path: Path = Path('cookie/cookies.txt')


@dataclass(frozen=True)
class DownloadOutcome:
    """Stable adapter output that does not expose yt-dlp metadata."""

    video_id: str
    title: str
    source_url: str
    artifacts: DownloadedArtifacts


def youtube_download_policy(retry_policy=None):
    return DownloadPolicy(
        retry_policy=retry_policy or RetryPolicy(),
        scheduled_notice=True,
        require_metadata=True,
        require_thumbnail=True,
        live_from_start=True,
        use_cookie_file=False,
    )


def generic_download_policy():
    return DownloadPolicy(
        retry_policy=None,
        scheduled_notice=False,
        require_metadata=False,
        require_thumbnail=False,
        live_from_start=False,
        use_cookie_file=True,
    )


def default_download_dependencies(settings):
    return DownloadDependencies(
        ydl_factory=yt_dlp.YoutubeDL,
        now=datetime.datetime.now,
        sleep=time.sleep,
        path_exists=Path.exists,
        make_directory=Path.mkdir,
        move=shutil.move,
        tmp_path=Path(settings.TMP_PATH),
        save_path=Path(settings.SAVE_PATH),
    )


def build_output_name(info, now):
    replacements = {
        '\\': '＼',
        '/': '／',
        '"': '”',
        "'": '’',
        ':': '：',
        '<': '＜',
        '>': '＞',
        '|': '｜',
        '?': '？',
    }
    return (
        f"{now.strftime('%Y-%m-%d-%H%M')}_{info['id']}"
        .translate(str.maketrans(replacements))
    )


class DownloadEngine:
    def __init__(self, dependencies, policy):
        self.dependencies = dependencies
        self.policy = policy

    def get_info(self, url):
        with self.dependencies.ydl_factory() as ydl:
            return ydl.extract_info(url, download=False)

    def data_check(self, url, info_loader=None):
        info_loader = info_loader or self.get_info
        try:
            info = info_loader(url)
        except yt_dlp.utils.DownloadError as error:
            if self.policy.scheduled_notice:
                notice = youtube_scheduled_notice(error)
                if notice is not None:
                    return notice
            raise
        return f"Video title : {info['title']}\nDownload start..."

    def download_video(
        self,
        url,
        info_loader=None,
        cancellation_token=None,
    ):
        self._raise_if_cancelled(cancellation_token)
        info_loader = info_loader or self.get_info
        info = self._load_download_info(
            url,
            info_loader,
            cancellation_token,
        )
        self._raise_if_cancelled(cancellation_token)
        title = build_output_name(info, self.dependencies.now())
        tmp_path = self.dependencies.tmp_path
        self.dependencies.ensure_directory(tmp_path)
        outpath = tmp_path / f'{title}.%(ext)s'

        with self.dependencies.ydl_factory(
            self.build_options(
                str(outpath),
                cancellation_token=cancellation_token,
            ),
        ) as ydl:
            self._raise_if_cancelled(cancellation_token)
            downloaded_info = ydl.extract_info(url, download=True)
            self._raise_if_cancelled(cancellation_token)
            artifacts = discover_download_artifacts(
                info=downloaded_info,
                ydl=ydl,
                output_stem=tmp_path / title,
                path_exists=self.dependencies.path_exists,
                require_metadata=self.policy.require_metadata,
                require_thumbnail=self.policy.require_thumbnail,
            )

        self._raise_if_cancelled(cancellation_token)
        stored_artifacts = self._move_artifacts(artifacts)
        return DownloadOutcome(
            video_id=str(downloaded_info.get('id') or ''),
            title=str(
                downloaded_info.get('fulltitle')
                or downloaded_info.get('title')
                or downloaded_info.get('id')
                or url
            ),
            source_url=str(
                downloaded_info.get('webpage_url')
                or downloaded_info.get('original_url')
                or url
            ),
            artifacts=stored_artifacts,
        )

    def _load_download_info(self, url, info_loader, cancellation_token):
        retry_policy = self.policy.retry_policy
        if retry_policy is None:
            self._raise_if_cancelled(cancellation_token)
            return info_loader(url)

        attempts = 0
        waited_seconds = 0
        while True:
            self._raise_if_cancelled(cancellation_token)
            attempts += 1
            try:
                return info_loader(url)
            except (
                yt_dlp.utils.DownloadError,
                yt_dlp.utils.ExtractorError,
                KeyError,
            ) as error:
                decision = retry_policy.decide(error)
                if decision.status is RetryStatus.PERMANENT_FAILURE:
                    raise PermanentDownloadError(
                        'Download failure is not retryable',
                        original_error=error,
                        attempts=attempts,
                        waited_seconds=waited_seconds,
                    ) from error

                wait_seconds = decision.wait_seconds
                if (
                    attempts >= retry_policy.max_attempts
                    or waited_seconds + wait_seconds
                    > retry_policy.max_wait_seconds
                ):
                    raise DownloadRetryLimitExceeded(
                        'Download retry limit exceeded',
                        original_error=error,
                        attempts=attempts,
                        waited_seconds=waited_seconds,
                    ) from error
                if cancellation_token is not None:
                    cancellation_token.wait(wait_seconds)
                else:
                    self.dependencies.sleep(wait_seconds)
                waited_seconds += wait_seconds

    def _move_artifacts(self, artifacts):
        save_path = self.dependencies.save_path
        metadata_path = save_path / 'metadata'
        thumbnail_path = save_path / 'thumbnail'
        self.dependencies.ensure_directory(save_path)
        self.dependencies.ensure_directory(metadata_path)
        self.dependencies.ensure_directory(thumbnail_path)

        move_plan = [
            (
                artifacts.video,
                save_path,
                save_path / artifacts.video.name,
            ),
            *(
                (
                    metadata,
                    metadata_path,
                    metadata_path / metadata.name,
                )
                for metadata in artifacts.metadata
            ),
            *(
                (
                    thumbnail,
                    thumbnail_path,
                    thumbnail_path / thumbnail.name,
                )
                for thumbnail in artifacts.thumbnails
            ),
        ]
        for _, _, destination in move_plan:
            if self.dependencies.path_exists(destination):
                raise shutil.Error(
                    f'Destination path already exists: {destination}',
                )

        completed_moves = []
        try:
            for source, destination_directory, destination in move_plan:
                self.dependencies.move(source, destination_directory)
                completed_moves.append((source, destination))
        except Exception as move_error:
            rollback_errors = []
            for source, destination in reversed(completed_moves):
                try:
                    self.dependencies.move(destination, source)
                except Exception as rollback_error:
                    rollback_errors.append(rollback_error)
            if rollback_errors:
                move_error.add_note(
                    'Failed to roll back one or more artifact moves: '
                    + '; '.join(str(error) for error in rollback_errors),
                )
            raise
        return DownloadedArtifacts(
            video=move_plan[0][2],
            metadata=tuple(
                metadata_path / path.name
                for path in artifacts.metadata
            ),
            thumbnails=tuple(
                thumbnail_path / path.name
                for path in artifacts.thumbnails
            ),
        )

    @staticmethod
    def _raise_if_cancelled(cancellation_token):
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

    def live_timer(self, info):
        if type(info) == dict:
            return 0
        if self.policy.retry_policy is not None:
            decision = self.policy.retry_policy.decide(info)
            if decision.status is RetryStatus.RETRYABLE:
                return decision.wait_seconds
        else:
            wait_seconds = youtube_scheduled_delay(info)
            if wait_seconds is not None:
                return wait_seconds
        raise info

    def build_options(self, outpath, cancellation_token=None):
        options = {
            'outtmpl': outpath,
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mkv',
            'noplaylist': True,
            'nooverwrites': True,
            'keepvideo': False,
            'hls_use_mpegts': True,
            'writeinfojson': True,
            'embed_metadata': True,
            'writethumbnail': True,
            'embedthumbnail': True,
            'socket_timeout': 300,
            'fragment_retries': 300,
            'postprocessor_args': {
                'videoconvertor': ['-c:v', 'copy'],
            },
            'postprocessors': [
                {
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                },
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                },
                {
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': True,
                },
            ],
        }
        if self.policy.live_from_start:
            options['live_from_start'] = True
        if (
            self.policy.use_cookie_file
            and self.dependencies.path_exists(self.policy.cookie_path)
        ):
            options['cookiefile'] = str(self.policy.cookie_path)
        if cancellation_token is not None:
            options['progress_hooks'] = [
                lambda _: cancellation_token.raise_if_cancelled(),
            ]
        return options

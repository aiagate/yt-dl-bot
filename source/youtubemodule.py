#! ./.venv/bin/python

# ---standard library---
import datetime
import time
import shutil
from pathlib import Path

# ---third party library---
import yt_dlp

# ---local library---
from artifact_discovery import discover_download_artifacts
from download_service import (
    DownloadDependencies,
    DownloadRetryLimitExceeded,
    PermanentDownloadError,
    RetryPolicy,
    RetryStatus,
)
from external_error_adapter import youtube_scheduled_notice
from setting import Settings
from url_validation import extract_youtube_video_id


class YoutubeModule():
    def __init__(self, dependencies=None, retry_policy=None, settings=None):
        if dependencies is None:
            settings = settings or Settings()
            dependencies = DownloadDependencies(
                ydl_factory=yt_dlp.YoutubeDL,
                now=datetime.datetime.now,
                sleep=time.sleep,
                path_exists=Path.exists,
                make_directory=Path.mkdir,
                move=shutil.move,
                tmp_path=Path(settings.TMP_PATH),
                save_path=Path(settings.SAVE_PATH),
            )
        self.dependencies = dependencies
        self.retry_policy = retry_policy or RetryPolicy()

    def data_check(self, url):
        #URLから動画情報を抽出
        try:
            info = self.get_info(url=url)

            #動画情報の抽出が正常終了した場合、メッセージを返す
            title = '%(title)s' % info
            message = 'Video title : ' + title + '\n' \
                      'Download start...'
            return message
        except yt_dlp.utils.DownloadError as e:
            notice = youtube_scheduled_notice(e)
            if notice is not None:
                return notice
            raise

    def download_video(self, url):
        is_download = False
        attempts = 0
        waited_seconds = 0

        #ライブ配信の場合、ライブ開始まで待機
        while is_download != True:
            attempts += 1
            try:
                #ダウンロード処理
                info = self.get_info(url)
                is_download = True
                break
            except yt_dlp.utils.DownloadError as e: #動画URLが有効でない場合にエラーを返す
                info = e
            except yt_dlp.utils.ExtractorError as e: #動画の抽出に失敗した場合は待機するため処理を続行する
                info = e
            except KeyError as e: # プレミア公開時のキーエラーを無視
                info = e
            #待機時間を計算しジョブを待機させる
            decision = self.retry_policy.decide(info)
            if decision.status is RetryStatus.PERMANENT_FAILURE:
                raise PermanentDownloadError(
                    'Download failure is not retryable',
                    original_error=info,
                    attempts=attempts,
                    waited_seconds=waited_seconds,
                ) from info

            sleeptime = decision.wait_seconds
            if (
                attempts >= self.retry_policy.max_attempts
                or waited_seconds + sleeptime
                > self.retry_policy.max_wait_seconds
            ):
                raise DownloadRetryLimitExceeded(
                    'Download retry limit exceeded',
                    original_error=info,
                    attempts=attempts,
                    waited_seconds=waited_seconds,
                ) from info

            self.dependencies.sleep(sleeptime)
            waited_seconds += sleeptime

        # is_download==True の場合、ダウンロード処理を開始する
        if is_download == True:
            now = self.dependencies.now()

            #ファイルパス・ファイル名を作成
            date = now.strftime('%Y-%m-%d-%H%M')
            ng_word = {
                '\\': '＼',
                '/': '／',
                '\"': '”',
                '\'': '’',
                ':': '：',
                '<': '＜',
                '>': '＞',
                '|': '｜',
                '?': '？',
            }
            info.setdefault('fulltitle', info['title'])
            title = date + '_%(id)s' % info
            title = title.translate(str.maketrans(ng_word))
            tmp_path = self.dependencies.tmp_path
            self.dependencies.ensure_directory(tmp_path)
            outpath = tmp_path / f'{title}.%(ext)s'

            with self.dependencies.ydl_factory(
                self.ops(info=info, outpath=str(outpath)),
            ) as ydl:
                info = ydl.extract_info(url, download=True)
                artifacts = discover_download_artifacts(
                    info=info,
                    ydl=ydl,
                    output_stem=tmp_path / title,
                    path_exists=self.dependencies.path_exists,
                    require_metadata=True,
                    require_thumbnail=True,
                )

            #ファイルをcacheフォルダから移動
            save_path = self.dependencies.save_path
            metadata_path = save_path / 'metadata'
            thumbnail_path = save_path / 'thumbnail'
            self.dependencies.ensure_directory(save_path)
            self.dependencies.move(artifacts.video, save_path)
            self.dependencies.ensure_directory(metadata_path)
            for metadata in artifacts.metadata:
                self.dependencies.move(metadata, metadata_path)
            self.dependencies.ensure_directory(thumbnail_path)
            for thumbnail in artifacts.thumbnails:
                self.dependencies.move(thumbnail, thumbnail_path)
            return info
    def get_info(self, url):
        with self.dependencies.ydl_factory() as ydl:
            info = ydl.extract_info(url, download=False)
        return info

    def live_timer(self, info):
        if type(info) == dict:
            return 0
        decision = self.retry_policy.decide(info)
        if decision.status is RetryStatus.RETRYABLE:
            return decision.wait_seconds
        raise info

    def ops(self, info, outpath):
        ydl_ops = {
            "outtmpl": outpath,
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
            'live_from_start': True,
            'socket_timeout': 300,
            "fragment_retries": 300,
            'postprocessor_args': {
                'videoconvertor': ['-c:v', 'copy']
            }, 
            'postprocessors':[
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
                }
            ],
        }
        return ydl_ops

    def get_videoid(self, url):
        return extract_youtube_video_id(url)


if __name__ == "__main__":
    import json
    ydm = YoutubeModule()
    # url = input('URL: ')
    url = 'https://youtu.be/_vl8MJc7oHI'
    try:
        info = ydm.get_info(url)
        print('%(is_live)s' % info)
        print(info['channel'])
        print(info.keys())
        print(info['release_timestamp'])
        print(info['duration'])
        # print(json.dumps(info, indent=2))
    except Exception as e:
        print('==================================================================')
        print(type(e))
        print('==================================================================')

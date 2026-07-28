#! ./.venv/bin/python

# ---standard library---
import datetime
import time
import shutil
from pathlib import Path

# ---third party library---
import yt_dlp

# ---local library---
from download_service import DownloadDependencies
from external_error_adapter import error_detail, youtube_scheduled_delay
from setting import Settings
from url_validation import extract_youtube_video_id


class YtdlpModule():
    def __init__(self, dependencies=None, settings=None):
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

    def data_check(self, url, ydl_ops={}):
        #URLから動画情報を抽出
        info = self.get_info(url=url)

        #動画情報の抽出が正常終了した場合、メッセージを返す
        title = '%(title)s' % info
        message = 'Video title : ' + title + '\n' \
                  'Download start...'
        return message

    def download_video(self, url, ops={}):
        now = self.dependencies.now()
        info = self.get_info(url)

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
            self.ops(outpath=str(outpath)),
        ) as ydl:
            info = ydl.extract_info(url, download=True)

        # ファイルをcacheフォルダから移動
        save_path = self.dependencies.save_path
        metadata_path = save_path / 'metadata'
        thumbnail_path = save_path / 'thumbnail'
        # フォルダがない場合は作成
        self.dependencies.ensure_directory(save_path)
        self.dependencies.ensure_directory(metadata_path)
        self.dependencies.ensure_directory(thumbnail_path)

        if self.dependencies.path_exists(tmp_path / f'{title}.mp4'):
            self.dependencies.move(tmp_path / f'{title}.mp4', save_path)
        if self.dependencies.path_exists(tmp_path / f'{title}.info.json'):
            self.dependencies.move(
                tmp_path / f'{title}.info.json',
                metadata_path,
            )
        if self.dependencies.path_exists(tmp_path / f'{title}.webp'):
            self.dependencies.move(
                tmp_path / f'{title}.webp',
                thumbnail_path,
            )
        if self.dependencies.path_exists(tmp_path / f'{title}.jpg'):
            self.dependencies.move(
                tmp_path / f'{title}.jpg',
                thumbnail_path,
            )
        if self.dependencies.path_exists(tmp_path / f'{title}.jpeg'):
            self.dependencies.move(
                tmp_path / f'{title}.jpeg',
                thumbnail_path,
            )

        return info

    def get_info(self, url):
        with self.dependencies.ydl_factory() as ydl:
            info = ydl.extract_info(url, download=False)
        return info

    def live_timer(self, info):
        if type(info) == dict:
            return 0
        wait_seconds = youtube_scheduled_delay(info)
        if wait_seconds is not None:
            return wait_seconds
        raise info

    def ops(self, outpath):
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
            # 'live_from_start': True,
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
        cookie_path = Path('cookie') / 'cookies.txt'
        if self.dependencies.path_exists(cookie_path):
            ydl_ops['cookiefile'] = str(cookie_path)
        return ydl_ops

    def get_videoid(self, url):
        return extract_youtube_video_id(url)


if __name__ == "__main__":
    ydm = YoutubeModule()
    url = input('URL: ')
    try:
        info = ydm.get_info(url)
        print('%(is_live)s' % info)
    except Exception as e:
        print('==================================================================')
        print(type(e))
        print('==================================================================')
        print(error_detail(e))
        print('==================================================================')
    # print(type(title))
    # message = ydm.live_timer(info)
    # print(message)

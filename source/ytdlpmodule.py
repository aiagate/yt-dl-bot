#! ./.venv/bin/python

# ---standard library---
import datetime
import time
import os
import shutil

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
                path_exists=os.path.exists,
                make_directory=os.mkdir,
                move=shutil.move,
                tmp_path=settings.TMP_PATH,
                save_path=settings.SAVE_PATH,
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
        if not self.dependencies.path_exists(tmp_path):
            self.dependencies.make_directory(tmp_path)
        outpath = f'{tmp_path}{title}.%(ext)s'
        with self.dependencies.ydl_factory(self.ops(outpath=outpath)) as ydl:
            info = ydl.extract_info(url, download=True)

        # ファイルをcacheフォルダから移動
        save_path = self.dependencies.save_path
        # フォルダがない場合は作成
        if not self.dependencies.path_exists(save_path):
            self.dependencies.make_directory(save_path)
        if not self.dependencies.path_exists(f"{save_path}metadata/"):
            self.dependencies.make_directory(f"{save_path}metadata/")
        if not self.dependencies.path_exists(f'{save_path}thumbnail/'):
            self.dependencies.make_directory(f'{save_path}thumbnail/')

        if self.dependencies.path_exists(f'{tmp_path}{title}.mp4'):
            self.dependencies.move(f'{tmp_path}{title}.mp4', f'{save_path}')
        if self.dependencies.path_exists(f'{tmp_path}{title}.info.json'):
            self.dependencies.move(
                f'{tmp_path}{title}.info.json',
                f'{save_path}metadata/',
            )
        if self.dependencies.path_exists(f'{tmp_path}{title}.webp'):
            self.dependencies.move(
                f'{tmp_path}{title}.webp',
                f'{save_path}thumbnail/',
            )
        if self.dependencies.path_exists(f'{tmp_path}{title}.jpg'):
            self.dependencies.move(
                f'{tmp_path}{title}.jpg',
                f'{save_path}thumbnail/',
            )
        if self.dependencies.path_exists(f'{tmp_path}{title}.jpeg'):
            self.dependencies.move(
                f'{tmp_path}{title}.jpeg',
                f'{save_path}thumbnail/',
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
        cookie_path = 'cookie/cookies.txt'
        if self.dependencies.path_exists(cookie_path):
            ydl_ops['cookiefile'] = cookie_path
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

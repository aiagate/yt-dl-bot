#! ./.venv/bin/python

# ---standard library---
import datetime
import time
import urllib
import os
import shutil

# ---third party library---
import yt_dlp

# ---local library---
import property
from download_service import DownloadDependencies


class YtdlpModule():
    def __init__(self, dependencies=None):
        self.dependencies = dependencies or DownloadDependencies(
            ydl_factory=yt_dlp.YoutubeDL,
            now=datetime.datetime.now,
            sleep=time.sleep,
            path_exists=os.path.exists,
            make_directory=os.mkdir,
            move=shutil.move,
            tmp_path=property.TMP_PATH,
            save_path=property.SAVE_PATH,
        )

    def data_check(self, url, ydl_ops={}):

        #URLから動画情報を抽出
        try:
            info = self.get_info(url=url)

            #動画情報の抽出が正常終了した場合、メッセージを返す
            title = '%(title)s' % info
            message = 'Video title : ' + title + '\n' \
                      'Download start...'
            return message
        except Exception as e:
            raise e

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
        elif type(info) == yt_dlp.utils.DownloadError:
            if 'This live event will begin in' in str(info.args) or 'Premiere' in str(info.args):

                # 'ERROR: This live event will begin in 77 minutes.'
                # 'ERROR: Premieres in 7 hours'
                args = str(info.args).split()
                time = -1
                for arg in args:
                    try:
                        time = int(arg) - 0.5
                    except:
                        if 'days' in arg:
                            time = time * 86400
                        elif 'hours' in arg:
                            time = time * 3600
                        elif 'minutes' in arg:
                            time = time * 60
                        elif 'few' in arg:
                            time = 15
                        elif 'shortly' in arg:
                            time = 15
                        else:
                            pass
                if time >= 0:
                    return time
                else:
                    raise info
            else:
                raise info
        else:
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
        parsed_url = urllib.parse.urlparse(url)
        video_id = urllib.parse.parse_qs(parsed_url.query)['v']
        return ''.join(video_id)


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
        print(e.args)
        print('==================================================================')
        print(e.exc_info)
        print('==================================================================')
        print(type(e.exc_info[0]))
        print(e.exc_info[0])
        print('==================================================================')
        print(type(e.exc_info[1]))
        print(e.exc_info[1])
        print('==================================================================')
        print(type(e.exc_info[2]))
        print(e.exc_info[2])
        print('==================================================================')
    # print(type(title))
    # message = ydm.live_timer(info)
    # print(message)

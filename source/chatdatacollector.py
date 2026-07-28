#! .venv/bin/python
# -*- coding: utf-8 -*-

# ---standard library---
import asyncio
import concurrent.futures
from datetime import datetime
import logging
from logging import DEBUG, INFO, Logger, getLogger
import json
import csv
import os
import time

# ---third party library---
import yt_dlp

# ---local library---
from sql_connect import DatabaseConnect
from youtubeapi import YoutubeApi
from chatdatamodule import ChatDataModule
import property

class ChatDataCollector():
    def __init__(self) -> None:
        self.logger = getLogger(__name__)
        self.videolist_table = 'yt_videolist'
        self.chatdata_table = 'yt_chatdata'
        self.ytdl_ops = {'extract_flat': True}
        cookie_path = 'cookie/cookies.txt'
        if os.path.exists(cookie_path):
            self.ytdl_ops['cookiefile'] = cookie_path

        with DatabaseConnect('youtube_chat') as db:
            try:
                db.cursor.execute(f'CREATE TABLE IF NOT EXISTS {self.videolist_table} ' + property.VIDEO_DATALIST)
                db.cursor.execute(f'CREATE TABLE IF NOT EXISTS {self.chatdata_table} ' + property.CHAT_DATALIST)
            except Exception as e:
                raise e

    def _extract_info(self, url, ydl_ops=None, retries=5, retry_delay=10, **kwargs):
        """Extract metadata with bounded retries or re-raise the last error."""
        last_error = None
        for attempt in range(retries):
            try:
                with yt_dlp.YoutubeDL(ydl_ops or {}) as ydl:
                    return ydl.extract_info(url, download=False, **kwargs)
            except Exception as error:
                last_error = error
                self.logger.error(error)
                if attempt < retries - 1:
                    time.sleep(retry_delay)

        raise last_error

    def get_videolist(self, channel_id):
        # Youtube-DLから動画情報を取得
        info = self._extract_info(
            f'https://www.youtube.com/channel/{channel_id}',
            ydl_ops=self.ytdl_ops,
            retry_delay=20,
        )
        self.logger.info(json.dumps(info, indent=4))

        videos = []
        entries = info.get('entries') or []
        if not entries:
            self.logger.info('No videos found for channel %s', channel_id)
            return
        if entries[0].get('_type') == 'url':
            videos = entries
        else:
            playlists = list(filter(lambda x: x.get('_type') == 'playlist', entries))
            for playlist in playlists:
                videos.extend(playlist['entries'])

        # self.logger.info(json.dumps(videos, indent=4))

        # is_all_url_type = all([video.get('_type') == 'url' for video in videos])
        # self.logger.info(f'is_all_url_type: {is_all_url_type}')

        # is_all_youtube = all([video.get('ie_key') == 'Youtube' for video in videos])
        # self.logger.info(f'is_all_youtube: {is_all_youtube}')

        for video in videos:
            with DatabaseConnect('youtube_chat') as db:
                try:
                    db.cursor.execute(
                        f'SELECT video_id FROM {self.videolist_table} '
                        'WHERE video_id = %s LIMIT 1;',
                        (video.get('id'),),
                    )
                    data = db.cursor.fetchone()
                    if data != None:
                        self.logger.info(data)
                        self.logger.info(f'{video.get("id")} skip! this video is getted!')
                        continue
                except Exception as e:
                    raise e

            self.logger.info(f'extract {video.get("id")} info.')

            title       = video.get('title')
            description = video.get('description')
            duration = video.get('duration')
            view_count = video.get('view_count')
            is_live     = True if video.get('live_status') == 'was_live' else False

            sql = f'INSERT INTO {self.videolist_table} VALUES (%s, %s, %s, %s, %s, %s, %s)'
            with DatabaseConnect('youtube_chat') as db:
                try:
                    db.cursor.execute(sql,(video.get('id'), channel_id, title, description, duration, view_count, is_live))
                except Exception as e:
                    raise e

    def update_videolist(self, channel_id):
        ytm = YoutubeApi()
        video_id_lists = ytm.get_video_list(channel_id, maxResults=50)
        with DatabaseConnect('youtube_chat') as db:
            for video_id in video_id_lists:
                try:
                    db.cursor.execute(
                        f'SELECT COUNT(video_id) FROM {self.videolist_table} '
                        'WHERE video_id = %s;',
                        (video_id,),
                    )
                except Exception as e:
                    raise e
                if db.cursor.fetchone()[0] != 0:
                    self.logger.info(f'{video_id} is getted!')
                    break

                info = self._extract_info(
                    f'https://youtu.be/{video_id}',
                    ie_key='Generic',
                )
                self.logger.debug(json.dumps(info, indent=4))

                if info.get('is_live') is True:
                    self.logger.info(f'{info.get("id")} skip! video has live now. ')
                    continue

                title       = info.get('fulltitle')
                description = info.get('description')
                timestamp   = datetime.fromtimestamp(int(info.get('release_timestamp'))) if info.get('release_timestamp') != None else datetime.strptime(info.get('upload_date') , '%Y%m%d')
                is_live     = info.get('was_live')
                live_chat   = 'live_chat' in info.get('subtitles').keys() if info.get('subtitles') != None else False

                sql = f'INSERT INTO {self.videolist_table} VALUES (%s, %s, %s, %s, %s, %s, %s)'
                with DatabaseConnect('youtube_chat') as db:
                    try:
                        db.cursor.execute(sql,(info.get('id'), channel_id, title, description, timestamp.strftime('%Y-%m-%d %H:%M:%S'), is_live, live_chat))
                    except Exception as e:
                        raise e

    # def create_chatdatabase(self):
    async def create_chatdatabase(self):
        with DatabaseConnect('youtube_chat') as db:
            try:
                db.cursor.execute(f'SELECT video_id FROM {self.videolist_table} WHERE is_live = True')
                # db.cursor.execute(f'select video_id from {self.videolist_table} WHERE not exists (SELECT DISTINCT video_id FROM {self.chatdata_table} WHERE {self.chatdata_table}.video_id = {self.videolist_table}.video_id) and {self.videolist_table}.live_chat = True;')
                # db.cursor.execute(f'select video_id from {self.videolist_table} WHERE {self.videolist_table}.live_chat = True;')
                video_id_list = db.cursor.fetchall()
            except Exception as e:
                raise e
        loop = asyncio.get_running_loop()

        if not video_id_list:
            return

        gather = []
        max_workers = min(16, len(video_id_list))
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            for video_id in video_id_list:
                with DatabaseConnect('youtube_chat') as db:
                    try:
                        db.cursor.execute(
                            f'SELECT id FROM {self.chatdata_table} '
                            'WHERE video_id = %s LIMIT 1;',
                            (video_id[0],),
                        )
                        data = db.cursor.fetchone()
                        if data != None:
                            self.logger.info(f'{video_id[0]} skip! this video chat data is getted!')
                            continue
                    except Exception as e:
                        raise e
                cdm = ChatDataModule(video_id[0], 0)
                gather.append(loop.run_in_executor(executor, cdm.create_chatdata))
            await asyncio.gather(*gather)

    async def input_channel_list(self):
        with open('databases/channel_id.csv', 'r', encoding='utf-8') as f:
            reader = csv.reader(filter(lambda row: row[0]!='#', f))#, comment='#')
            channels = [row for row in reader]
        loop = asyncio.get_running_loop()
        gather = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=16) as executor:
            for channel in channels:
                self.logger.info(f'{channel[0]}:{channel[1]}')
                gather.append(loop.run_in_executor(executor, self.get_videolist, channel[0]))
            await asyncio.gather(*gather)

if __name__ == '__main__':
    logging.basicConfig(
        level=INFO,
        format='[ %(levelname)-8s] %(asctime)s | %(name)-32s %(funcName)-24s| %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    log_path = property.COLLECTOR_LOG_PATH
    if not os.path.exists(log_path):
        os.mkdir(log_path)

    fh = logging.FileHandler(filename=f'{log_path}/chat_data_search_system.log', encoding='utf-8')
    fh.setLevel=INFO
    fh.setFormatter(logging.Formatter('[ %(levelname)-8s] %(asctime)s | %(name)-32s %(funcName)-24s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

    logger = getLogger(__name__)
    logger.addHandler(fh)

    cdc = ChatDataCollector()

    # cdc.get_videolist('UCIG9rDtgR45VCZmYnd-4DUw') # プティ
    # cdc.create_videolist('UCSFCh5NL4qXrAy9u-u2lX3g') # 葛葉
    # cdc.create_videolist('UCspv01oxUFf_MTSipURRhkA') # 叶
    # cdc.create_videolist('UCLO9QDxVL4bnvRRsz6K4bsQ') # ちひろ
    # cdc.create_videolist('UCb5JxV6vKlYVknoJB8TnyYg') # 黛
    # cdc.create_videolist('UCzUNASdzI4PV5SlqtYwAkKQ') # めと
    # cdc.create_videolist('UCIu-aUArYq_H84dBpCAokMA') # レイド
    # cdc.create_videolist('UC5LyYg6cCA4yHEYvtUsir3g') # うるは
    # cdc.create_videolist('UCyLGcqYs7RsBb3L0SJfzGYA') # すみれ
    # cdc.create_videolist('UCiMG6VdScBabPhJ1ZtaVmbw') # なずな
    # cdc.create_videolist('UCgTzsBI0DIRopMylJEDqnog') # とと

    # cdc.get_videolist('UCWAlDdbQee8AEyY7n65ulUA') # WhiteTails 2016-01-22
    # cdc.get_videolist('UCoqRFblrxE8BQzE_Fs2K9jw') # Nakamu 2020-04-09
    # cdc.get_videolist('UChBKIvOv1UQxuV23GkbV5nA') # ぶるーく 2020-05-16
    # cdc.get_videolist('UCZFJb6rn_1H-rLFLcixQOLQ') # シャークん 2020-04-09
    # cdc.get_videolist('UCoIoxmP0i8KOAMyEfM0ORkA') # きんとき 2020-04-09
    # cdc.get_videolist('UCj8L3CH25EAqkXjFOMdwk7w') # スマイル 2020-06-20
    # cdc.get_videolist('UCM2_EXlU8F5d9axobMvlGtg') # きりやん 2020-04-9

    # cdc.get_videolist('UCD5W21JqNMv_tV9nfjvF9sw') # 紫宮
    # cdc.get_videolist('UCPkKpOHxEDcwmUAnRpIu-Ng') # 藍沢エマ 2021-09-18

    # cdc.get_videolist('UCufQu4q65z63IgE4cfKs1BQ') # 語部紡

    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(cdc.input_channel_list())

    loop = asyncio.get_event_loop()
    loop.run_until_complete(cdc.create_chatdatabase())

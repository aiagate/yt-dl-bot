#! ./.venv/bin/python

# ---standard library---
import datetime
import importlib
import logging
from logging import getLogger
from multiprocessing import Pool
import os
import shutil
import time
import unicodedata
import json

# ---third party library---
import ffmpeg
import matplotlib.pyplot as plt
from pytchat import create
from collections import deque

# ---local library---
import db_connect
import property
from sql_connect import DatabaseConnect


class ChatDataModule():
    def __init__(self, video_id, starttime):
        self.logger = getLogger(__name__)
        importlib.reload(importlib)
        importlib.reload(db_connect)
        self.url = f'https://youtu.be/{video_id}'
        self.starttime = int(
            datetime.datetime
                .fromtimestamp(starttime)
                .replace(tzinfo=datetime.timezone(datetime.timedelta(hours=9)))
                .timestamp() * 1000
            )
        self.video_id = video_id
        self.date = datetime.datetime.now().strftime('%Y-%m-%d-%H%M')
        self.db_name = os.getcwd() + '/databases/chatdata_' + \
            self.date + '_' + video_id + '.db'
        self.image_name = 'scoregraph_' + self.date + '_' + video_id + '.png'
        self.image_path = os.getcwd() + '/downloads/' + self.image_name
        self.table_name = 'yt_chatdata'

    def count_score(self):
        seektime = self.starttime
        endtime = 0
        score_data = []
        average_count = deque([1000] * 8)

        with db_connect.DatabaseConnect(db_name=self.db_name) as db:
            try:
                endtimeResult = db.execute('select timestamp from chatdata order by timestamp desc limit 1')
                endtime = endtimeResult.fetchone()[0]
                sampleResult = db.execute('select * from chatdata order by timestamp desc limit 1')
                print(sampleResult.fetchone())
            except Exception as e:
                raise e

        self.logger.info(f'Video start time [{seektime}]')
        self.logger.info(f'Video end time [{endtime}]')

        while seektime + 60000 <= endtime:
            with db_connect.DatabaseConnect(db_name=self.db_name) as db:
                try:
                    result = db.execute(
                        'select type,message from chatdata where ? < timestamp and timestamp < ?', seektime, seektime + 30000)
                    result_data = result.fetchall()
                except Exception as e:
                    raise e
            score = len(result_data)

            comment_count = len(result_data)

            if comment_count > 0:
                score = score / (sum(average_count) / len(average_count))

                average_count.append(comment_count)
                average_count.popleft()

            self.logger.debug(f'score: {score}')
            score_data.append(score)
            seektime = seektime + 30000
        return score_data

    def plot_peak(self, score_data):
        max_score = max(score_data)
        score_size = len(score_data)

        plt.figure()
        plt.plot([i * 30 for i in list(range(score_size))], score_data)
        plt.grid(axis='y', linestyle='dotted')
        plt.savefig(self.image_path)

    def get_peaktime(self, score_data):
        max_score = max(score_data)
        score_size = len(score_data)

        peaktime = []
        i = 0
        limit = 0.3
        while i < score_size:
            if score_data[i] > max_score * limit:
                peaktime_sec = max(i - 1, 0)
                l = 2
                while l >= 0 and i < score_size:
                    if score_data[i] > max_score * limit:
                        l = 2
                    else:
                        l = l - 1
                    i = i + 1
                peaktime_sec = peaktime_sec * 30
                peaktime.append(peaktime_sec)
            i = i + 1
        return peaktime

    def get_chatdata(self):

        with db_connect.DatabaseConnect(db_name=self.db_name) as db:
            try:
                # db.execute('drop table if exists chatdata')
                db.execute('create table if not exists chatdata ' +
                           property.CHAT_LITE)
            except Exception as e:
                raise e

        with db_connect.DatabaseConnect(db_name=self.db_name) as db:
            chat = create(video_id=self.video_id)
            while chat.is_alive():
                try:
                    data = chat.get()
                    items = data.items
                    for c in items:
                        sql = 'insert into chatdata values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)'
                        db.execute(sql,
                            c.id,
                            c.author.name,
                            c.author.channelId,
                            c.type,
                            c.message,
                            c.datetime,
                            c.timestamp,
                            c.amountValue,
                            c.amountString,
                            c.currency,
                            c.author.isVerified,
                            c.author.isChatOwner,
                            c.author.isChatSponsor,
                            c.author.isChatModerator)

                except KeyboardInterrupt:
                    chat.terminate()
                    break
                except Exception as e:
                    chat.terminate()
                    raise e
            time.sleep(3)
        return 'Success!'

    def create_chatdata(self):
        video_id = self.video_id
        chat = create(video_id=video_id, force_replay=True)
        if chat.is_replay:
            pass
        else:
            self.logger.info('live now! skip!')
            return
        with DatabaseConnect('youtube_chat') as db:
            while chat.is_alive():
                try:
                    data = chat.get()
                    items = data.items
                    for c in items:
                        elapsedTimeStr = c.elapsedTime.replace(',','').split(':')
                        elapsedTime = 0
                        if (len(elapsedTimeStr) == 3): elapsedTime = int(elapsedTimeStr[0])*3600 + int(elapsedTimeStr[1])*60 + int(elapsedTimeStr[2])
                        elif (len(elapsedTimeStr) == 2): elapsedTime = int(elapsedTimeStr[0])*60 + int(elapsedTimeStr[1])
                        elif (len(elapsedTimeStr) == 1):
                            try: elapsedTime = int(elapsedTimeStr[0])
                            except:elapsedTime = 0
                        else:elapsedTime = 0

                        # self.logger.info(f"{c.datetime} | {c.elapsedTime} {elapsedTime} [{c.author.name}]- {c.message}")
                        author_name_width = 0
                        for name_c in c.author.name:
                            author_name_width += 1 if unicodedata.east_asian_width(name_c) in 'FWA' else 0
                        # print(f"{c.datetime.split()[0]:>10} {c.datetime.split()[1]:>8} | {c.elapsedTime:>8} {elapsedTime:>5} | [{c.author.name:^{24-max(0,author_name_width)}}] {c.message}")
                        sql = f'INSERT INTO {self.table_name} (\
                            id,\
                            video_id,\
                            name,\
                            channel_id,\
                            type,\
                            message,\
                            datetime,\
                            elapsed_time,\
                            amount_value,\
                            amount_string,\
                            currency,\
                            is_verified,\
                            is_owner,\
                            is_sponsor,\
                            is_moderator\
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
                        value = (
                            c.id,
                            video_id,
                            c.author.name,
                            c.author.channelId,
                            c.type,
                            c.message,
                            datetime.datetime.strptime(c.datetime, '%Y-%m-%d %H:%M:%S'),
                            elapsedTime,
                            c.amountValue,
                            c.amountString,
                            c.currency,
                            c.author.isVerified,
                            c.author.isChatOwner,
                            c.author.isChatSponsor,
                            c.author.isChatModerator,
                        )
                        db.cursor.execute(sql, value)
                except KeyboardInterrupt:
                    chat.terminate()
                    break
                except Exception as e:
                    print(e)
                    chat.terminate()
                    break
        return

    def cut_movie(self, file_path, title, date, pool):
        self.logger.debug(f'video id: {self.video_id}')
        pool.wait()
        cut_time = self.get_peaktime(self.count_score())
        self.logger.debug(f'video id: {cut_time}')

        for time in cut_time:
            start_time = time[0]
            end_time = time[1]
            filename = date + '_' + self.video_id + '_' + title + \
                '_' + str(start_time) + '-' + str(end_time) + '.mkv'
            save_path = os.getcwd() + '/tmp/' + filename

            video_info = ffmpeg.probe(file_path)
            duration = float(video_info['format']['duration'])

            start_time = min(start_time, duration)
            stride = min(end_time, duration) - start_time

            stream = ffmpeg.input(file_path, ss=start_time, t=stride)
            stream = ffmpeg.output(stream, save_path, c="copy")
            stream = ffmpeg.overwrite_output(stream)
            try:
                ffmpeg.run(stream, capture_stdout=True, capture_stderr=True)
                video_save_path = os.path.join(property.SAVE_PATH, date[:10])
                os.makedirs(video_save_path, exist_ok=True)
                shutil.move(save_path, os.path.join(video_save_path, filename))
            except ffmpeg.Error as e:
                database_name = 'chatdata_' + self.date + '_' + self.video_id + '.db'
                database_path = 'databases/'
                out_path = property.CHAT_DATA_SAVE_PATH
                if not os.path.exists(out_path):
                    os.mkdir(out_path)
                shutil.move(database_path + database_name,
                            out_path + database_name)
                os.remove(file_path)
                raise e

        database_name = 'chatdata_' + self.date + '_' + self.video_id + '.db'
        database_path = 'databases/'
        out_path = property.CHAT_DATA_SAVE_PATH
        os.makedirs(out_path, exist_ok=True)
        shutil.move(database_path + database_name, out_path + database_name)
        os.remove(file_path)

    def get_highlight(self):
        pool = Pool(1)
        result = pool.apply_async(self.get_chatdata)

        self.logger.info('get chat')
        result.wait()
        self.logger.info('sleep')

        self.logger.info('get score')
        score_data = self.count_score()
        self.logger.info(f'score data: {score_data}')
        self.plot_peak(score_data)
        self.logger.debug('get peaktime')

        peak_times = self.get_peaktime(score_data)
        highlight_urls = []
        for sec in peak_times:
            url = self.url + '&t=' + str(sec) + 's'
            self.logger.info(f'url: {url}')
            highlight_urls.append([sec, url])
        out_path = property.CHAT_DATA_SAVE_PATH
        if not os.path.exists(out_path):
            os.mkdir(out_path)
        shutil.move(self.db_name, out_path)
        self.logger.debug('move database')
        return highlight_urls


if __name__ == '__main__':
    import logging
    from logging import DEBUG, INFO, Logger, getLogger
    logging.basicConfig(
        level=INFO,
        format='[ %(levelname)-8s] %(asctime)s | %(name)-24s %(funcName)-16s| %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    # id = input('ID:')
    # cdm = ChatDataModule('xTx37448l34', 1622568354)
    cdm = ChatDataModule('xTx37448l34', 1615881830)

    # 1622568354000
    # 1622574380844
    cdm.create_chatdata()
    cdm.get_highlight()

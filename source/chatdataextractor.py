#! .venv/bin/python
# -*- coding: utf-8 -*-

# ---standard library---
import datetime
import logging
from logging import getLogger

# ---third party library---

# ---local library---
from sql_connect import DatabaseConnect
import property


class ChatDataExtractor():
    def __init__(self):
        self.logger = getLogger(__name__)
        self.date = datetime.datetime.now().strftime('%Y-%m-%d-%H%M')
        self.table_name = 'yt_chatdata'
    
    def search_video_keyword(self, keyword):
        with DatabaseConnect('youtube_chat') as db:
            try:
                db.cursor.execute(f'SELECT DISTINCT video_id FROM {self.table_name} where message like \"%{keyword}%\";')
                result = db.cursor.fetchall()
            except Exception as e:
                raise e
        video_ids = []
        for video_id in result:
            video_ids.append(video_id)
        return video_ids

    def extract_from_keyword(self, video_id, keyword, minscore=0):
        with DatabaseConnect('youtube_chat') as db:
            try:
                # self.logger.debug(f'drop table if exists {self.table_name}')
                # db.cursor.execute(f'DROP TABLE IF EXISTS {self.table_name}')
                
                db.cursor.execute(f'SELECT elapsed_time FROM {self.table_name} where video_id = \"{video_id}\" AND message like \"%{keyword}%\" order by elapsed_time;')
                result = db.cursor.fetchall()
            except Exception as e:
                raise e
        nexttime = 0
        search_result = []
        for elapsedTime in result:
            t = int(elapsedTime[0])
            if (t < 0):
                continue
            elif (t > nexttime):
                seektime = t
                nexttime = t + 10
                score = 1
                for endtime in result:
                    if (seektime < endtime[0] and endtime[0] < nexttime):
                        nexttime += 10
                        score += 1
                        continue
                    elif (endtime[0] > nexttime):
                        break
                if (score < minscore): break
                url = f'https://youtu.be/{video_id}'
                search_result.append(f'{url}?t={seektime - property.SEEK_TIME_OFFSET} score={score}')
                self.logger.info(f'Search Result {url}?t={seektime - property.SEEK_TIME_OFFSET} score={score}')
        return search_result
        
    

if __name__ == '__main__':
    import logging
    from logging import DEBUG, INFO, Logger, getLogger
    logging.basicConfig(
        level=INFO,
        format='[ %(levelname)-8s] %(asctime)s | %(name)-24s %(funcName)-16s| %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    fh = logging.FileHandler(filename='log/chat_data_search_system.log', encoding='utf-8')
    fh.setLevel=DEBUG
    fh.setFormatter(logging.Formatter('[ %(levelname)-8s] %(asctime)s | %(name)-32s %(funcName)-24s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

    logger = getLogger(__name__)
    logger.addHandler(fh)

    cde = ChatDataExtractor()
    cde.extract_from_keyword('U_4GveY98Jk', 'くしゃみ')#,input('keyword:'))

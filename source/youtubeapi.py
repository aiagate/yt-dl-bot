#! ./.venv/bin/python

# ---standard library---
from datetime import datetime as dt

# ---third party library---
from googleapiclient.discovery import build

# ---local library---
import property

API_KEY = property.YOUTUBE_API_KEY
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

class YoutubeApi():

    def __init__(self):
        self.youtube = build(
            API_SERVICE_NAME,
            API_VERSION,
            developerKey = API_KEY
        )

    def search_live(self, channel_id):
        response = self.youtube.search().list(
            part = 'id',
            channelId = channel_id,
            eventType = 'live',
            type = 'video'
        ).execute()
        return response

    def get_livedetail(self, video_id):
        response = self.youtube.videos().list(
            part = 'snippet,liveStreamingDetails',
            id = video_id
        ).execute()
        if 'liveStreamingDetails' not in response['items'][0].keys():
            raise
        return response

    def get_channel_name(self, response):
        name = response['items'][0]['snippet']['channelTitle']
        return name

    def get_title(self, response):
        title = response['items'][0]['snippet']['title']
        return title

    def get_thumbnail_url(self, response):
        url = response['items'][0]['snippet']['thumbnails']['maxres']['url']
        return url

    def get_islive(self, response):
        try:
            is_live = response['items'][0]['snippet']['liveBroadcastContent']
            if is_live == 'none':
                is_live = False
            elif is_live == 'live':
                is_live = True
            else:
                is_live = False
                # raise # 何が来るかよくわからんのでFalse
        except:
            raise
        return is_live

    def get_starttime(self, response):
        try:
            actualStartTime = response['items'][0]['liveStreamingDetails']['actualStartTime']
        except:
            actualStartTime = '1970-01-01 00:00:00Z'
        return actualStartTime

    def get_endtime(self, response):
        try:
            actualEndTime = response['items'][0]['liveStreamingDetails']['actualEndTime']
        except:
            actualEndTime = '1970-01-01 00:00:00Z'
        return actualEndTime

    def get_starttime_UNIX(self, response):
        start_time = self.get_starttime(response=response)
        start_time = start_time.replace('T', ' ').replace('Z', '') + '+0000'
        start_time_UNIX = int(dt.strptime(start_time, '%Y-%m-%d %H:%M:%S%z').timestamp() * 1000)
        return start_time_UNIX

    def get_endtime_UNIX(self, response):
        end_time = self.get_endtime(response=response)
        end_time = end_time.replace('T', ' ').replace('Z', '') + '+0000'
        end_time_UNIX = int(dt.strptime(end_time, '%Y-%m-%d %H:%M:%S%z').timestamp() * 1000)
        return end_time_UNIX
    
    def get_Live(self, channel_id):
        response = self.youtube.liveBroadcasts().list(
            part = 'contentDetails',
            channelId = channel_id
        ).execute()
        return response


if __name__ == "__main__":
    api = YoutubeApi()
    # res = api.search_live(input())
    res = api.get_livedetail(input('id:'))
    # '''
    print(api.get_starttime_UNIX(res))
    print(api.get_endtime_UNIX(res))
    print(api.get_starttime(res))
    print(api.get_endtime(res))
    # print(type(res))
    # print(res)
    '''
    for item in res.get('items', []):
        print(json.dumps(item['liveStreamingDetails'], indent=2, ensure_ascii=False))
        print(item['snippet']['liveBroadcastContent'])
        print(api.get_islive(res))
    # '''
    # actualStartTime = res['items'][0]['liveStreamingDetails']['actualStartTime']
    # print(res.get('liveStreamingDetails'))
    # print(res['liveStreamingDetails']['actualStartTime'])
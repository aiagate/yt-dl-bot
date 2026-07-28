import datetime
import os
from collections import deque
from logging import getLogger

import matplotlib.pyplot as plt
from pytchat import create

from setting import Settings


class ChatDataModule:
    """Detect chat activity peaks without persisting individual comments."""

    BUCKET_SECONDS = 30

    def __init__(self, video_id, settings=None):
        settings = settings or Settings()
        self.logger = getLogger(__name__)
        self.video_id = video_id
        self.url = f'https://youtu.be/{video_id}'
        date = datetime.datetime.now().strftime('%Y-%m-%d-%H%M')
        self.image_name = f'scoregraph_{date}_{video_id}.png'
        self.image_path = os.path.join(settings.TMP_PATH, self.image_name)

    @staticmethod
    def _elapsed_seconds(elapsed_time):
        parts = elapsed_time.replace(',', '').split(':')
        try:
            values = [int(part) for part in parts]
        except (TypeError, ValueError):
            return None

        if len(values) == 3:
            return values[0] * 3600 + values[1] * 60 + values[2]
        if len(values) == 2:
            return values[0] * 60 + values[1]
        if len(values) == 1:
            return values[0]
        return None

    def collect_comment_counts(self):
        """Return comment counts grouped into 30-second buckets."""
        counts = []
        chat = create(video_id=self.video_id, force_replay=True)
        try:
            while chat.is_alive():
                for comment in chat.get().items:
                    elapsed = self._elapsed_seconds(comment.elapsedTime)
                    if elapsed is None or elapsed < 0:
                        continue
                    bucket = elapsed // self.BUCKET_SECONDS
                    if bucket >= len(counts):
                        counts.extend([0] * (bucket + 1 - len(counts)))
                    counts[bucket] += 1
        finally:
            chat.terminate()
        return counts

    def count_score(self, comment_counts):
        score_data = []
        average_count = deque([1000] * 8)
        for comment_count in comment_counts:
            score = 0
            if comment_count > 0:
                score = comment_count / (sum(average_count) / len(average_count))
                average_count.append(comment_count)
                average_count.popleft()
            score_data.append(score)
        return score_data

    def plot_peak(self, score_data):
        os.makedirs(os.path.dirname(self.image_path), exist_ok=True)
        figure = plt.figure()
        plt.plot(
            [index * self.BUCKET_SECONDS for index in range(len(score_data))],
            score_data,
        )
        plt.grid(axis='y', linestyle='dotted')
        figure.savefig(self.image_path)
        plt.close(figure)

    def get_peaktime(self, score_data):
        if not score_data or max(score_data) <= 0:
            return []

        max_score = max(score_data)
        peak_times = []
        index = 0
        while index < len(score_data):
            if score_data[index] > max_score * 0.3:
                peak_index = max(index - 1, 0)
                quiet_buckets = 2
                while quiet_buckets >= 0 and index < len(score_data):
                    if score_data[index] > max_score * 0.3:
                        quiet_buckets = 2
                    else:
                        quiet_buckets -= 1
                    index += 1
                peak_times.append(peak_index * self.BUCKET_SECONDS)
            index += 1
        return peak_times

    def get_highlight(self):
        self.logger.info('Collecting chat activity for %s', self.video_id)
        comment_counts = self.collect_comment_counts()
        score_data = self.count_score(comment_counts)
        self.plot_peak(score_data)

        highlights = []
        for seconds in self.get_peaktime(score_data):
            url = f'{self.url}?t={seconds}s'
            self.logger.info('Highlight: %s', url)
            highlights.append([seconds, url])
        return highlights

import sys
import unittest
from pathlib import Path


SOURCE_PATH = Path(__file__).resolve().parents[1] / 'source'
sys.path.insert(0, str(SOURCE_PATH))

from url_validation import (
    extract_youtube_video_id,
    identify_service,
    parse_youtube_video_url,
    validate_service_url,
)


class IdentifyServiceTest(unittest.TestCase):
    def test_accepts_supported_youtube_urls(self):
        urls = (
            'https://www.youtube.com/watch?v=video-id&list=playlist-id',
            'https://youtube.com/shorts/video-id',
            'https://m.youtube.com/watch?v=video-id',
            'https://music.youtube.com/watch?v=video-id',
            'https://youtu.be/video-id?t=10',
            'http://youtu.be/video-id',
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(identify_service(url), 'youtube')

    def test_accepts_supported_twitch_urls(self):
        urls = (
            'https://www.twitch.tv/channel',
            'https://twitch.tv/videos/123',
            'https://m.twitch.tv/channel',
            'https://clips.twitch.tv/ClipSlug',
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(identify_service(url), 'twitch')

    def test_rejects_malformed_or_unsafe_input(self):
        values = (
            '',
            'not a url',
            'www.youtube.com/watch?v=video-id',
            'ftp://www.youtube.com/watch?v=video-id',
            'javascript://www.youtube.com/%0Aalert(1)',
            'https://localhost/watch?v=video-id',
            'https://127.0.0.1/watch?v=video-id',
            'https://[::1]/watch?v=video-id',
            'https://www.youtube.com:443/watch?v=video-id',
            'https://www.twitch.tv:8443/channel',
            'https://user@www.youtube.com/watch?v=video-id',
            'https://user:password@www.twitch.tv/channel',
            'https://www.youtube.com:invalid/watch?v=video-id',
            None,
        )

        for value in values:
            with self.subTest(value=value):
                self.assertIsNone(identify_service(value))

    def test_rejects_host_spoofing(self):
        urls = (
            'https://youtube.com.example.org/watch?v=video-id',
            'https://www.youtube.com.evil.test/watch?v=video-id',
            'https://evil-youtube.com/watch?v=video-id',
            'https://twitch.tv.example.org/channel',
            'https://www.twitch.tv@evil.test/channel',
            'https://youtube．com/watch?v=video-id',
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertIsNone(identify_service(url))


class ValidateServiceUrlTest(unittest.TestCase):
    def test_returns_stripped_url_without_removing_query_parameters(self):
        url = 'https://youtu.be/video-id?t=10&feature=share'

        self.assertEqual(
            validate_service_url(f'  {url}  ', 'youtube'),
            url,
        )

    def test_rejects_wrong_service(self):
        with self.assertRaisesRegex(ValueError, 'Invalid youtube URL'):
            validate_service_url('https://www.twitch.tv/channel', 'youtube')

    def test_rejects_unknown_service(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported service'):
            validate_service_url('https://www.youtube.com/watch?v=id', 'other')


class YoutubeVideoIdTest(unittest.TestCase):
    VIDEO_ID = 'dQw4w9WgXcQ'

    def test_extracts_id_from_supported_video_forms(self):
        urls = (
            f'https://www.youtube.com/watch?v={self.VIDEO_ID}',
            f'https://youtube.com/watch?v={self.VIDEO_ID}&list=playlist',
            f'https://m.youtube.com/watch?v={self.VIDEO_ID}&t=10',
            f'https://music.youtube.com/watch?v={self.VIDEO_ID}',
            f'https://youtu.be/{self.VIDEO_ID}?si=tracking',
            f'https://www.youtube.com/shorts/{self.VIDEO_ID}',
            f'https://www.youtube.com/live/{self.VIDEO_ID}?feature=share',
            f'https://www.youtube.com/embed/{self.VIDEO_ID}',
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(
                    extract_youtube_video_id(url),
                    self.VIDEO_ID,
                )

    def test_returns_a_canonical_watch_url(self):
        reference = parse_youtube_video_url(
            f'  https://youtu.be/{self.VIDEO_ID}?si=tracking  ',
        )

        self.assertEqual(reference.video_id, self.VIDEO_ID)
        self.assertEqual(
            reference.canonical_url,
            f'https://www.youtube.com/watch?v={self.VIDEO_ID}',
        )

    def test_rejects_non_video_and_empty_id_urls(self):
        urls = (
            'https://www.youtube.com/playlist?list=PL123',
            'https://www.youtube.com/watch?list=PL123',
            'https://www.youtube.com/watch?v=',
            'https://youtu.be/',
            'https://www.youtube.com/shorts/',
            'https://www.youtube.com/live/',
            'https://www.youtube.com/embed/',
        )

        for url in urls:
            with self.subTest(url=url):
                with self.assertRaisesRegex(
                    ValueError,
                    'Invalid YouTube video URL',
                ):
                    extract_youtube_video_id(url)

    def test_rejects_ambiguous_or_extra_paths(self):
        urls = (
            f'https://www.youtube.com/watch/extra?v={self.VIDEO_ID}',
            f'https://youtu.be/{self.VIDEO_ID}/extra',
            f'https://youtu.be/{self.VIDEO_ID}/',
            f'https://www.youtube.com/shorts/{self.VIDEO_ID}/extra',
            f'https://www.youtube.com/live/{self.VIDEO_ID}/extra',
            f'https://www.youtube.com/embed/{self.VIDEO_ID}/extra',
            (
                'https://www.youtube.com/watch?'
                f'v={self.VIDEO_ID}&v=otherVideo1'
            ),
        )

        for url in urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    extract_youtube_video_id(url)

    def test_rejects_invalid_ids_and_spoofed_hosts(self):
        urls = (
            'https://www.youtube.com/watch?v=bad%2Fid',
            'https://www.youtube.com/watch?v=bad.id',
            'https://www.youtube.com/watch?v=%20',
            f'https://youtube.com.evil.test/watch?v={self.VIDEO_ID}',
            f'https://www.youtube.com@evil.test/watch?v={self.VIDEO_ID}',
            f'https://localhost/watch?v={self.VIDEO_ID}',
            f'https://www.youtube.com:443/watch?v={self.VIDEO_ID}',
        )

        for url in urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    extract_youtube_video_id(url)


if __name__ == '__main__':
    unittest.main()

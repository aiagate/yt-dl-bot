import json
import unittest
from pathlib import Path

import yt_dlp


PROJECT_ROOT = Path(__file__).resolve().parents[1]

from yt_dl_bot.external_error_adapter import (
    ExternalErrorKind,
    is_twitch_offline,
    parse_external_error,
    youtube_scheduled_delay,
)


class ExternalErrorAdapterTest(unittest.TestCase):
    def test_observed_external_messages_are_classified(self):
        fixture_path = (
            PROJECT_ROOT / 'tests' / 'fixtures'
            / 'external_error_messages.json'
        )
        cases = json.loads(fixture_path.read_text())

        for case in cases:
            with self.subTest(case['name']):
                if case['type'] == 'download':
                    error = yt_dlp.utils.DownloadError(case['message'])
                else:
                    error = RuntimeError('extract failed')
                    error.exc_info = (
                        None,
                        RuntimeError(case['message']),
                        None,
                    )

                parsed = parse_external_error(error)

                self.assertEqual(parsed.kind.value, case['kind'])
                self.assertEqual(parsed.retryable, case['retryable'])
                self.assertEqual(
                    parsed.wait_seconds,
                    case['wait_seconds'],
                )
                self.assertTrue(parsed.reason)
                self.assertEqual(parsed.detail, case['message'])

    def test_unknown_message_is_permanent_for_retry_policy(self):
        error = yt_dlp.utils.DownloadError(
            'This live event was postponed until further notice.',
        )

        parsed = parse_external_error(error)

        self.assertIs(parsed.kind, ExternalErrorKind.UNKNOWN)
        self.assertFalse(parsed.retryable)
        self.assertIsNone(youtube_scheduled_delay(error))
        self.assertEqual(
            parsed.reason,
            'no_known_external_error_pattern',
        )

    def test_legacy_twitch_helper_uses_structured_classification(self):
        error = RuntimeError('The channel is not currently live')

        self.assertTrue(is_twitch_offline(error))

import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx

SCRIPT = Path(__file__).parents[1] / "scripts" / "external_smoke.py"
SPEC = importlib.util.spec_from_file_location("external_smoke", SCRIPT)
assert SPEC and SPEC.loader
external_smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(external_smoke)


class ExternalSmokeValidationTest(unittest.TestCase):
    def test_defaults_are_credential_free_public_targets(self):
        self.assertEqual(
            external_smoke.DEFAULT_YTDLP_URL,
            "https://www.w3schools.com/html/mov_bbb.mp4",
        )
        self.assertEqual(external_smoke.DEFAULT_PYTCHAT_VIDEO_ID, "4xnApfWvjXs")

    def test_metadata_requires_identity_title_and_formats(self):
        info = {"id": "video", "title": "title", "formats": [{"format_id": "one"}]}

        self.assertIs(external_smoke.require_metadata(info, "video"), info)

    def test_metadata_rejects_unexpected_identity(self):
        with self.assertRaisesRegex(external_smoke.SmokeFailure, "expected"):
            external_smoke.require_metadata(
                {"id": "other", "title": "title", "formats": [{}]}, "video"
            )

    def test_chat_batch_requires_replay_messages(self):
        self.assertEqual(external_smoke.require_chat_batch(True, [object()]), 1)

        with self.assertRaisesRegex(external_smoke.SmokeFailure, "archived"):
            external_smoke.require_chat_batch(False, [object()])
        with self.assertRaisesRegex(external_smoke.SmokeFailure, "empty"):
            external_smoke.require_chat_batch(True, [])

    def test_ffprobe_requires_stream_and_postprocessing_metadata(self):
        payload = {
            "streams": [{"codec_name": "aac"}],
            "format": {"tags": {"title": "yt-dl-bot smoke"}},
        }

        self.assertIs(external_smoke.require_ffprobe(payload), payload)

        with self.assertRaisesRegex(external_smoke.SmokeFailure, "metadata"):
            external_smoke.require_ffprobe({"streams": [{}], "format": {"tags": {}}})

    def test_failure_report_is_machine_readable_without_network(self):
        with self.assertRaises(SystemExit):
            external_smoke.parse_args(["yt-dlp", "--attempts", "0"])

    def test_cli_caps_external_attempts_at_three(self):
        self.assertEqual(external_smoke.parse_args(["pytchat", "--attempts", "3"]).attempts, 3)
        with self.assertRaises(SystemExit):
            external_smoke.parse_args(["pytchat", "--attempts", "4"])

    @patch.object(external_smoke.subprocess, "run")
    def test_ffmpeg_stage_validates_postprocessed_output(self, run):
        probe_payload = {
            "streams": [{"codec_name": "aac"}],
            "format": {"tags": {"title": "yt-dl-bot smoke"}},
        }

        def run_command(command, **_kwargs):
            if command[0] == "ffmpeg":
                Path(command[-1]).write_bytes(b"synthetic audio")
                return subprocess.CompletedProcess(command, 0)
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(probe_payload),
                stderr="",
            )

        run.side_effect = run_command

        report = external_smoke.smoke_ffmpeg()

        self.assertEqual(report["stage"], "ffmpeg postprocessing")
        self.assertEqual(report["bytes"], len(b"synthetic audio"))
        self.assertEqual(run.call_count, 2)

    def test_report_file_contains_json(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            external_smoke.write_report("ffmpeg", {"status": "passed"}, Path(directory))

            self.assertEqual(
                json.loads((Path(directory) / "ffmpeg.json").read_text()),
                {"status": "passed"},
            )


class PytchatSmokeTest(unittest.TestCase):
    def chat(self, items, held_error=None):
        batch = SimpleNamespace(
            items=items,
            sync_items=Mock(side_effect=AssertionError("smoke must not wait for playback")),
        )
        chat = Mock(spec=["get", "raise_for_status", "is_replay", "terminate"])
        chat.get.return_value = batch
        chat.raise_for_status.side_effect = held_error
        chat.is_replay.return_value = True
        return chat

    def test_nonempty_batch_is_checked_without_playback_wait_and_is_cleaned_up(self):
        chat = self.chat([object(), object()])
        with patch("pytchat.create", return_value=chat) as create:
            report = external_smoke.smoke_pytchat("video", attempts=1)

        self.assertEqual(report, {"stage": "pytchat replay", "target": "video", "message_count": 2})
        create.assert_called_once_with(video_id="video", force_replay=True)
        chat.get.assert_called_once_with()
        chat.get.return_value.sync_items.assert_not_called()
        chat.raise_for_status.assert_called_once_with()
        chat.terminate.assert_called_once_with()

    def test_empty_batches_fail_with_one_get_per_bounded_attempt_and_cleanup(self):
        chats = [self.chat([]) for _ in range(3)]
        with (
            patch("pytchat.create", side_effect=chats) as create,
            patch.object(external_smoke.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(external_smoke.SmokeFailure, "attempt 3.*empty"):
                external_smoke.smoke_pytchat("video", attempts=3)

        self.assertEqual(create.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        for chat in chats:
            chat.get.assert_called_once_with()
            chat.raise_for_status.assert_called_once_with()
            chat.get.return_value.sync_items.assert_not_called()
            chat.terminate.assert_called_once_with()

    def test_held_fetch_error_is_reported_before_empty_batch_validation(self):
        chat = self.chat([], RuntimeError("held fetch error"))
        with patch("pytchat.create", return_value=chat):
            with self.assertRaisesRegex(
                external_smoke.SmokeFailure, "RuntimeError: held fetch error"
            ):
                external_smoke.smoke_pytchat("video", attempts=1)

        chat.is_replay.assert_not_called()
        chat.terminate.assert_called_once_with()

    def test_get_exception_still_terminates_the_chat(self):
        chat = self.chat([])
        chat.get.side_effect = RuntimeError("get failed")
        with patch("pytchat.create", return_value=chat):
            with self.assertRaisesRegex(external_smoke.SmokeFailure, "get failed"):
                external_smoke.smoke_pytchat("video", attempts=1)

        chat.raise_for_status.assert_not_called()
        chat.terminate.assert_called_once_with()

    def test_retry_after_held_error_returns_the_successful_batch_and_cleans_up_both(self):
        failed = self.chat([], RuntimeError("held fetch error"))
        successful = self.chat([object()])
        with (
            patch("pytchat.create", side_effect=[failed, successful]),
            patch.object(external_smoke.time, "sleep") as sleep,
        ):
            report = external_smoke.smoke_pytchat("video", attempts=2)

        self.assertEqual(report["message_count"], 1)
        sleep.assert_called_once_with(3)
        failed.get.assert_called_once_with()
        successful.get.assert_called_once_with()
        failed.terminate.assert_called_once_with()
        successful.terminate.assert_called_once_with()


class PytchatChannelDiagnosticTest(unittest.TestCase):
    VIDEO_ID = "4xnApfWvjXs"
    CHANNEL_ID = "UC" + "x" * 22

    def run_diagnostic(self, responses):
        requests = []
        original_client = httpx.Client

        def handler(request):
            requests.append(request)
            response = responses[len(requests) - 1]
            if isinstance(response, Exception):
                raise response
            return response

        def client(**kwargs):
            return original_client(transport=httpx.MockTransport(handler), **kwargs)

        with patch("httpx.Client", side_effect=client):
            report = external_smoke.diagnose_pytchat_channel(self.VIDEO_ID)
        return report, requests

    def response(self, body, status=200, **headers):
        return httpx.Response(
            status,
            stream=httpx.ByteStream(body.encode()),
            headers={"content-type": "text/html", **headers},
        )

    def test_fallback_observes_patterns_without_logging_body_or_sending_cookies(self):
        from pytchat import config

        secret = "PRIVATE_VALUE_NEVER_LOG"
        with patch.dict(
            config.headers,
            {"authorization": secret, "cookie": secret, "proxy-authorization": secret},
        ):
            report, requests = self.run_diagnostic(
                [
                    self.response(secret, **{"set-cookie": f"session={secret}"}),
                    self.response(f'{{"channelId":"{self.CHANNEL_ID}","token":"{secret}"}}'),
                ]
            )

        self.assertEqual(len(requests), 2)
        self.assertEqual(report["outcome"], "channel_pattern_found")
        self.assertFalse(report["responses"][0]["pytchat_pattern_match"])
        self.assertTrue(report["responses"][1]["pytchat_pattern_match"])
        for request in requests:
            self.assertEqual(request.method, "GET")
            for header in ("cookie", "authorization", "proxy-authorization"):
                self.assertNotIn(header, request.headers)
        self.assertNotIn(secret, json.dumps(report))
        self.assertNotIn(self.CHANNEL_ID, json.dumps(report))

    def test_http_access_denial_stops_before_mobile_fallback(self):
        report, requests = self.run_diagnostic([self.response("blocked", status=429)])

        self.assertEqual(len(requests), 1)
        self.assertEqual(report["outcome"], "access_stop")
        self.assertEqual(report["responses"][0]["http_status"], 429)

    def test_bot_warning_stops_even_with_http_success(self):
        report, requests = self.run_diagnostic(
            [self.response("Sign in to confirm you're not a bot")]
        )

        self.assertEqual(len(requests), 1)
        self.assertEqual(report["outcome"], "access_stop")
        self.assertTrue(report["responses"][0]["refusal_features"]["bot_confirmation"])

    def test_consent_redirect_stops_without_following_or_logging_location(self):
        report, requests = self.run_diagnostic(
            [self.response("", status=302, location="https://consent.youtube.com/m?token=SECRET")]
        )

        self.assertEqual(len(requests), 1)
        self.assertEqual(report["outcome"], "access_stop")
        self.assertTrue(report["responses"][0]["consent_redirect"])
        self.assertNotIn("SECRET", json.dumps(report))

    def test_mobile_desktop_redirect_is_classified_and_not_followed(self):
        report, requests = self.run_diagnostic(
            [
                self.response(f'{{"channelId":"{self.CHANNEL_ID}"}}'),
                self.response("", status=302, location="https://www.youtube.com/watch?v=SECRET"),
            ]
        )

        self.assertEqual(len(requests), 2)
        self.assertTrue(report["responses"][0]["plain_channel_id_match"])
        self.assertFalse(report["responses"][0]["pytchat_pattern_match"])
        self.assertEqual(report["outcome"], "redirect_not_followed")
        self.assertTrue(report["responses"][1]["redirects_to_desktop_watch"])
        self.assertNotIn("SECRET", json.dumps(report))

    def test_oversized_body_stops_and_reports_only_bounded_prefix_length(self):
        report, requests = self.run_diagnostic(
            [self.response("x" * (external_smoke.CHANNEL_DIAGNOSTIC_BODY_LIMIT + 1))]
        )

        self.assertEqual(len(requests), 1)
        observed = report["responses"][0]
        self.assertEqual(
            observed["body_bytes_retained"], external_smoke.CHANNEL_DIAGNOSTIC_BODY_LIMIT
        )
        self.assertEqual(
            observed["body_bytes_received"], external_smoke.CHANNEL_DIAGNOSTIC_BODY_LIMIT + 1
        )
        self.assertTrue(observed["body_limit_hit"])
        self.assertFalse(observed["body_complete"])
        self.assertEqual(report["outcome"], "incomplete_or_http_error")

    def test_known_denial_and_compression_are_stopped_before_body_read(self):
        class UnreadableStream(httpx.SyncByteStream):
            def __iter__(self):
                raise AssertionError("body must not be read")

        for status, headers, outcome in (
            (403, {}, "access_stop"),
            (200, {"content-encoding": "gzip"}, "encoded_response_not_inspected"),
        ):
            with self.subTest(status=status):
                report, requests = self.run_diagnostic(
                    [httpx.Response(status, headers=headers, stream=UnreadableStream())]
                )
                self.assertEqual(len(requests), 1)
                self.assertEqual(report["outcome"], outcome)
                self.assertEqual(report["responses"][0]["body_bytes_received"], 0)
                self.assertFalse(report["responses"][0]["body_inspected"])

    def test_reaching_prefix_limit_stops_before_fetching_next_chunk(self):
        class LimitedStream(httpx.SyncByteStream):
            def __iter__(self):
                yield b"x" * external_smoke.CHANNEL_DIAGNOSTIC_BODY_LIMIT
                raise AssertionError("must stop before next chunk")

        report, requests = self.run_diagnostic([httpx.Response(200, stream=LimitedStream())])

        self.assertEqual(len(requests), 1)
        self.assertEqual(report["outcome"], "incomplete_or_http_error")
        self.assertEqual(
            report["responses"][0]["body_bytes_received"],
            external_smoke.CHANNEL_DIAGNOSTIC_BODY_LIMIT,
        )

    def test_small_slow_chunks_reach_deadline_without_internal_buffering(self):
        clock = [0]

        class SlowStream(httpx.SyncByteStream):
            def __iter__(self):
                for _ in range(30):
                    clock[0] += 7
                    yield b"x"

        with patch.object(external_smoke.time, "monotonic", side_effect=lambda: clock[0]):
            report, requests = self.run_diagnostic([httpx.Response(200, stream=SlowStream())])

        self.assertEqual(len(requests), 1)
        self.assertEqual(clock[0], 21)
        self.assertEqual(report["responses"][0]["body_bytes_received"], 3)
        self.assertEqual(report["responses"][0]["request_error"], "deadline_exceeded")

    def test_transport_exception_values_are_not_published(self):
        report, requests = self.run_diagnostic([httpx.ReadTimeout("token=SECRET")])

        self.assertEqual(len(requests), 1)
        self.assertEqual(report["responses"][0]["request_error"], "timeout")
        self.assertNotIn("SECRET", json.dumps(report))

    @patch.object(external_smoke, "write_report")
    @patch.object(external_smoke, "diagnose_pytchat_channel")
    def test_diagnostic_completion_is_observed_and_not_smoke_pass(self, diagnose, write):
        diagnose.return_value = {"outcome": "access_stop"}

        self.assertEqual(external_smoke.main(["pytchat-channel"]), 0)

        self.assertEqual(write.call_args.args[1]["status"], "observed")

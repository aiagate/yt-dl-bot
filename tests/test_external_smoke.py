import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

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

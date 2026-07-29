import importlib.util
import json
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "external_smoke.py"
SPEC = importlib.util.spec_from_file_location("external_smoke", SCRIPT)
assert SPEC and SPEC.loader
external_smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(external_smoke)


class ExternalSmokeValidationTest(unittest.TestCase):
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

    def test_ffmpeg_stage_runs_against_synthetic_input(self):
        report = external_smoke.smoke_ffmpeg()

        self.assertEqual(report["stage"], "ffmpeg postprocessing")
        self.assertGreater(report["bytes"], 0)

    def test_report_file_contains_json(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            external_smoke.write_report("ffmpeg", {"status": "passed"}, Path(directory))

            self.assertEqual(
                json.loads((Path(directory) / "ffmpeg.json").read_text()),
                {"status": "passed"},
            )

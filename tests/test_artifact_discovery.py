import unittest
from pathlib import Path

from yt_dl_bot.artifact_discovery import (
    ArtifactDiscoveryError,
    DownloadedArtifacts,
    discover_download_artifacts,
)


class FakeYoutubeDL:
    def __init__(self, prepared_filename):
        self.prepared_filename = prepared_filename

    def prepare_filename(self, _info):
        return self.prepared_filename


class ArtifactDiscoveryTest(unittest.TestCase):
    def discover(
        self,
        info,
        existing,
        *,
        prepared="/tmp/output.mp4",
        require_metadata=True,
        require_thumbnail=True,
    ):
        return discover_download_artifacts(
            info=info,
            ydl=FakeYoutubeDL(prepared),
            output_stem=Path("/tmp/output"),
            path_exists=lambda path: path in {Path(item) for item in existing},
            require_metadata=require_metadata,
            require_thumbnail=require_thumbnail,
        )

    def test_discovers_extension_variants_from_returned_info(self):
        info = {
            "filepath": "/tmp/output.mkv",
            "infojson_filename": "/tmp/output.info.json",
            "thumbnails": [
                {"filepath": "/tmp/output.jpg", "ext": "jpg"},
            ],
        }

        result = self.discover(
            info,
            {
                "/tmp/output.mkv",
                "/tmp/output.info.json",
                "/tmp/output.jpg",
            },
            prepared="/tmp/intermediate.webm",
        )

        self.assertEqual(
            result,
            DownloadedArtifacts(
                video=Path("/tmp/output.mkv"),
                metadata=(Path("/tmp/output.info.json"),),
                thumbnails=(Path("/tmp/output.jpg"),),
            ),
        )

    def test_prefers_final_filepath_when_multiple_video_candidates_exist(self):
        info = {
            "filepath": "/tmp/final.mp4",
            "requested_downloads": [
                {"filepath": "/tmp/intermediate.webm"},
            ],
            "infojson_filename": "/tmp/final.info.json",
            "thumbnails": [{"filepath": "/tmp/final.webp"}],
        }

        result = self.discover(
            info,
            {
                "/tmp/final.mp4",
                "/tmp/intermediate.webm",
                "/tmp/final.info.json",
                "/tmp/final.webp",
            },
        )

        self.assertEqual(result.video, Path("/tmp/final.mp4"))

    def test_uses_prepare_filename_when_final_path_is_not_reported(self):
        result = self.discover(
            {
                "infojson_filename": "/tmp/output.info.json",
                "thumbnails": [{"filepath": "/tmp/output.png"}],
            },
            {
                "/tmp/prepared.webm",
                "/tmp/output.info.json",
                "/tmp/output.png",
            },
            prepared="/tmp/prepared.webm",
        )

        self.assertEqual(result.video, Path("/tmp/prepared.webm"))

    def test_youtube_policy_reports_missing_required_sidecars(self):
        with self.assertRaises(ArtifactDiscoveryError) as raised:
            self.discover(
                {"filepath": "/tmp/output.mp4"},
                {"/tmp/output.mp4"},
            )

        self.assertEqual(
            raised.exception.missing,
            ("metadata", "thumbnail"),
        )

    def test_generic_policy_allows_missing_optional_sidecars(self):
        result = self.discover(
            {"filepath": "/tmp/output.webm"},
            {"/tmp/output.webm"},
            prepared="/tmp/output.webm",
            require_metadata=False,
            require_thumbnail=False,
        )

        self.assertEqual(result.video, Path("/tmp/output.webm"))
        self.assertEqual(result.metadata, ())
        self.assertEqual(result.thumbnails, ())

    def test_video_is_always_required(self):
        with self.assertRaises(ArtifactDiscoveryError) as raised:
            self.discover(
                {
                    "infojson_filename": "/tmp/output.info.json",
                    "thumbnails": [{"filepath": "/tmp/output.webp"}],
                },
                {
                    "/tmp/output.info.json",
                    "/tmp/output.webp",
                },
                require_metadata=False,
                require_thumbnail=False,
            )

        self.assertEqual(raised.exception.missing, ("video",))


if __name__ == "__main__":
    unittest.main()

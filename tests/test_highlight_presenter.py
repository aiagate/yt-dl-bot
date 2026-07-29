import unittest
from pathlib import Path

from yt_dl_bot.application_results import HighlightResult
from yt_dl_bot.cogs.highlight_presenter import (
    create_highlight_embed,
    format_highlight_fields,
)
from yt_dl_bot.highlight import Highlight


class HighlightPresenterTest(unittest.TestCase):
    def test_empty_highlights_get_a_placeholder(self):
        self.assertEqual(
            format_highlight_fields([]),
            ("does not get highlight",),
        )

    def test_highlight_text_is_split_before_field_limit(self):
        highlights = [
            Highlight(index, f"https://example.test/{index}/" + ("x" * 30)) for index in range(10)
        ]

        fields = format_highlight_fields(highlights, max_length=120)

        self.assertGreater(len(fields), 1)
        self.assertTrue(all(len(field) < 120 for field in fields))

    def test_single_line_at_field_limit_boundaries_is_always_safe(self):
        max_length = 40
        line_prefix = "0:00:01\t"
        newline_length = 1
        cases = (
            ("max_length_minus_one", max_length - 1, max_length - 1),
            ("exactly_max_length", max_length, max_length - 1),
            ("single_line_over_limit", max_length + 10, max_length - 1),
        )

        for name, line_length, expected_length in cases:
            with self.subTest(name=name):
                url = "x" * (line_length - len(line_prefix) - newline_length)

                fields = format_highlight_fields(
                    [Highlight(1, url)],
                    max_length=max_length,
                )

                self.assertEqual(len(fields), 1)
                self.assertEqual(len(fields[0]), expected_length)
                self.assertLess(len(fields[0]), max_length)

    def test_invalid_field_limit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least 2"):
            format_highlight_fields([], max_length=1)

    def test_embed_preserves_visible_highlight_output(self):
        result = HighlightResult(
            title="Title",
            channel_name="Channel",
            thumbnail_url="https://example.test/thumb.jpg",
            graph_image=Path("/tmp/graph.png"),
            highlights=(
                Highlight(30, "https://youtu.be/video-id?t=30s"),
                Highlight(90, "https://youtu.be/video-id?t=90s"),
            ),
        )

        embed = create_highlight_embed(result)

        self.assertEqual(embed.title, "Title")
        self.assertEqual(embed.description, "Channel")
        self.assertEqual(embed.color.value, 0xFF0000)
        self.assertEqual(embed.thumbnail.url, "https://example.test/thumb.jpg")
        self.assertEqual(embed.image.url, "attachment://image.png")
        self.assertEqual(
            [(field.name, field.value) for field in embed.fields],
            [
                (
                    "highlight",
                    "0:00:30\thttps://youtu.be/video-id?t=30s\n"
                    "0:01:30\thttps://youtu.be/video-id?t=90s\n",
                ),
            ],
        )

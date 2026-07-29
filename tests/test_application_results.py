import unittest

from yt_dl_bot.application_results import (
    split_highlight_text,
)
from yt_dl_bot.highlight import Highlight


class ApplicationResultsTest(unittest.TestCase):
    def test_empty_highlights_get_a_placeholder(self):
        self.assertEqual(
            split_highlight_text([]),
            ("does not get highlight",),
        )

    def test_highlight_text_is_split_before_field_limit(self):
        highlights = [
            Highlight(index, f"https://example.test/{index}/" + ("x" * 30)) for index in range(10)
        ]

        fields = split_highlight_text(highlights, max_length=120)

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

                fields = split_highlight_text(
                    [Highlight(1, url)],
                    max_length=max_length,
                )

                self.assertEqual(len(fields), 1)
                self.assertEqual(len(fields[0]), expected_length)
                self.assertLess(len(fields[0]), max_length)

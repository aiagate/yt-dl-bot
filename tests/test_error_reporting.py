import sys
import unittest
from pathlib import Path


SOURCE_PATH = Path(__file__).resolve().parents[1] / 'source'
sys.path.insert(0, str(SOURCE_PATH))

from error_reporting import (
    DISCORD_FIELDS_PER_EMBED,
    DISCORD_FIELD_VALUE_LIMIT,
    EMPTY_TRACEBACK_MESSAGE,
    format_exception_traceback,
    split_traceback_for_embeds,
)


class SplitTracebackForEmbedsTest(unittest.TestCase):
    def test_empty_traceback_uses_non_empty_fallback(self):
        self.assertEqual(
            split_traceback_for_embeds(''),
            ((EMPTY_TRACEBACK_MESSAGE,),),
        )

    def test_exact_field_boundary_is_one_field(self):
        error_log = 'x' * DISCORD_FIELD_VALUE_LIMIT

        batches = split_traceback_for_embeds(error_log)

        self.assertEqual(batches, ((error_log,),))

    def test_text_over_field_boundary_is_split_without_loss(self):
        error_log = 'x' * (DISCORD_FIELD_VALUE_LIMIT + 1)

        batches = split_traceback_for_embeds(error_log)
        chunks = tuple(chunk for batch in batches for chunk in batch)

        self.assertEqual(tuple(map(len, chunks)), (1024, 1))
        self.assertEqual(''.join(chunks), error_log)

    def test_long_traceback_respects_field_and_embed_boundaries(self):
        error_log = 'traceback\n' * 10_000

        batches = split_traceback_for_embeds(error_log)
        chunks = tuple(chunk for batch in batches for chunk in batch)

        self.assertTrue(
            all(len(batch) <= DISCORD_FIELDS_PER_EMBED for batch in batches),
        )
        self.assertTrue(
            all(len(chunk) <= DISCORD_FIELD_VALUE_LIMIT for chunk in chunks),
        )
        self.assertEqual(''.join(chunks), error_log)

    def test_invalid_limits_are_rejected(self):
        with self.assertRaises(ValueError):
            split_traceback_for_embeds('error', field_value_limit=0)
        with self.assertRaises(ValueError):
            split_traceback_for_embeds('error', fields_per_embed=0)


class FormatExceptionTracebackTest(unittest.TestCase):
    def test_formats_exception_with_complete_traceback(self):
        try:
            raise RuntimeError('boom')
        except RuntimeError as error:
            formatted = format_exception_traceback(error)

        self.assertIn('Traceback (most recent call last):', formatted)
        self.assertIn("raise RuntimeError('boom')", formatted)
        self.assertTrue(formatted.endswith('RuntimeError: boom\n'))


if __name__ == '__main__':
    unittest.main()

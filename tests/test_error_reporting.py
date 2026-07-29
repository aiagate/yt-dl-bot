import unittest

from yt_dl_bot.error_reporting import (
    DISCORD_FIELD_VALUE_LIMIT,
    DISCORD_FIELDS_PER_EMBED,
    EMPTY_TRACEBACK_MESSAGE,
    LOCAL_PATH,
    REDACTED,
    format_exception_traceback,
    sanitize_discord_error_report,
    split_traceback_for_embeds,
)


class SplitTracebackForEmbedsTest(unittest.TestCase):
    def test_empty_traceback_uses_non_empty_fallback(self):
        self.assertEqual(
            split_traceback_for_embeds(""),
            ((EMPTY_TRACEBACK_MESSAGE,),),
        )

    def test_exact_field_boundary_is_one_field(self):
        error_log = "x" * DISCORD_FIELD_VALUE_LIMIT

        batches = split_traceback_for_embeds(error_log)

        self.assertEqual(batches, ((error_log,),))

    def test_text_over_field_boundary_is_split_without_loss(self):
        error_log = "x" * (DISCORD_FIELD_VALUE_LIMIT + 1)

        batches = split_traceback_for_embeds(error_log)
        chunks = tuple(chunk for batch in batches for chunk in batch)

        self.assertEqual(tuple(map(len, chunks)), (1024, 1))
        self.assertEqual("".join(chunks), error_log)

    def test_long_traceback_respects_field_and_embed_boundaries(self):
        error_log = "traceback\n" * 10_000

        batches = split_traceback_for_embeds(error_log)
        chunks = tuple(chunk for batch in batches for chunk in batch)

        self.assertTrue(
            all(len(batch) <= DISCORD_FIELDS_PER_EMBED for batch in batches),
        )
        self.assertTrue(
            all(len(chunk) <= DISCORD_FIELD_VALUE_LIMIT for chunk in chunks),
        )
        self.assertEqual("".join(chunks), error_log)

    def test_invalid_limits_are_rejected(self):
        with self.assertRaises(ValueError):
            split_traceback_for_embeds("error", field_value_limit=0)
        with self.assertRaises(ValueError):
            split_traceback_for_embeds("error", fields_per_embed=0)


class FormatExceptionTracebackTest(unittest.TestCase):
    def test_formats_exception_with_complete_traceback(self):
        try:
            raise RuntimeError("boom")
        except RuntimeError as error:
            formatted = format_exception_traceback(error)

        self.assertIn("Traceback (most recent call last):", formatted)
        self.assertIn('raise RuntimeError("boom")', formatted)
        self.assertTrue(formatted.endswith("RuntimeError: boom\n"))


class SanitizeDiscordErrorReportTest(unittest.TestCase):
    def test_redacts_headers_and_common_key_value_credentials(self):
        report = (
            "Authorization: Bearer abc.def\n"
            "Cookie: sessionid=cookie-secret; preference=dark\n"
            "token='token-secret' password=hunter2 api_key: key-secret\n"
        )

        sanitized = sanitize_discord_error_report(report)

        self.assertNotIn("abc.def", sanitized)
        self.assertNotIn("cookie-secret", sanitized)
        self.assertNotIn("token-secret", sanitized)
        self.assertNotIn("hunter2", sanitized)
        self.assertNotIn("key-secret", sanitized)
        self.assertEqual(sanitized.count(REDACTED), 5)

    def test_redacts_url_credentials_and_sensitive_query_values(self):
        report = (
            "request failed: "
            "https://alice:password@example.test/watch?v=123&token=url-secret&quality=best"
        )

        sanitized = sanitize_discord_error_report(report)

        self.assertEqual(
            sanitized,
            "request failed: "
            f"https://{REDACTED}@example.test/watch?v=123&token={REDACTED}&quality=best",
        )
        self.assertNotIn("alice", sanitized)
        self.assertNotIn("password", sanitized)
        self.assertNotIn("url-secret", sanitized)

    def test_redacts_posix_and_windows_absolute_paths_but_keeps_filename(self):
        report = (
            '  File "/home/bot/private/project/worker.py", line 42\n'
            r"cache at C:\Users\bot\private\metadata.json failed"
        )

        sanitized = sanitize_discord_error_report(report)

        self.assertEqual(
            sanitized,
            f'  File "{LOCAL_PATH}/worker.py", line 42\ncache at {LOCAL_PATH}/metadata.json failed',
        )
        self.assertNotIn("/home/bot", sanitized)
        self.assertNotIn(r"C:\Users", sanitized)

    def test_preserves_debugging_context_and_non_sensitive_url_values(self):
        report = (
            "Traceback (most recent call last):\n"
            "RuntimeError: extractor failed for "
            "https://example.test/watch?v=video-id&quality=best\n"
        )

        self.assertEqual(sanitize_discord_error_report(report), report)

    def test_malformed_url_does_not_break_error_reporting(self):
        report = "request failed: https://user:secret@example.test:invalid/watch"

        sanitized = sanitize_discord_error_report(report)

        self.assertEqual(sanitized, "request failed: <redacted-url>")
        self.assertNotIn("secret", sanitized)

    def test_is_deterministic_and_idempotent(self):
        report = "token=secret in /srv/bot/app.py"
        once = sanitize_discord_error_report(report)

        self.assertEqual(sanitize_discord_error_report(report), once)
        self.assertEqual(sanitize_discord_error_report(once), once)


if __name__ == "__main__":
    unittest.main()

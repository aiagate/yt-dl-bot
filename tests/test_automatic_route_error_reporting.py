"""Automatic downloads report failures and preserve cancellation."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from yt_dl_bot.cogs.maincog import MainCog
from yt_dl_bot.video_download_service import TwitchStreamOffline


class AutomaticRouteErrorReportingTest(unittest.IsolatedAsyncioTestCase):
    def make_route(self, service_name, error=None):
        bot = Mock()
        bot.command_prefix = "!"
        bot.settings = SimpleNamespace(DOWNLOAD_CHANNEL=10, LOG_CHANNEL=30, VIDEO_OUTPUT_CHANNEL=40)
        bot.services = SimpleNamespace(youtube_download=Mock(), twitch_download=Mock())
        service = getattr(bot.services, service_name)
        service.check.side_effect = error
        channel = SimpleNamespace(mention="#errors", send=AsyncMock())
        bot.get_channel.return_value = channel
        url = (
            "https://www.twitch.tv/channel"
            if service_name == "twitch_download"
            else "https://youtu.be/video"
        )
        message = SimpleNamespace(
            content=url, author=SimpleNamespace(bot=False), channel=SimpleNamespace(id=10)
        )
        ctx = Mock()
        ctx.reply = AsyncMock()
        bot.get_context = AsyncMock(return_value=ctx)
        return MainCog(bot), message, ctx, channel

    async def test_service_failures_notify_user_and_log_for_both_sites(self):
        for service_name in ("youtube_download", "twitch_download"):
            with self.subTest(service=service_name):
                cog, message, ctx, channel = self.make_route(
                    service_name, RuntimeError("service unavailable")
                )
                await cog.on_message(message)
                ctx.reply.assert_awaited_once_with("Error: Check #errors")
                channel.send.assert_awaited_once()
                self.assertIn("service unavailable", cog.bot.logger.error.call_args.args[0])

    async def test_download_failure_after_initial_reply_notifies_user(self):
        cog, message, ctx, channel = self.make_route("youtube_download")
        cog.bot.services.youtube_download.check.return_value = "Starting download"
        cog.bot.services.youtube_download.download.side_effect = RuntimeError("download failed")
        await cog.on_message(message)
        self.assertEqual(
            [call.args[0] for call in ctx.reply.await_args_list],
            ["Starting download", "Error: Check #errors"],
        )
        channel.send.assert_awaited_once()

    async def test_twitch_offline_is_reported_without_error_log(self):
        cog, message, ctx, channel = self.make_route("twitch_download", TwitchStreamOffline())
        await cog.on_message(message)
        ctx.reply.assert_awaited_once_with("このチャンネルでライブは始まっていません。")
        channel.send.assert_not_awaited()
        cog.bot.services.twitch_download.download.assert_not_called()

    async def test_cancellation_propagates_without_error_notification(self):
        cog, message, ctx, channel = self.make_route("youtube_download", asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await cog.on_message(message)
        ctx.reply.assert_not_awaited()
        channel.send.assert_not_awaited()

"""Automatic URL failures must reach the same reporting path as commands."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from discord.ext import commands
from discord.ext.commands.view import StringView

from yt_dl_bot.cogs.maincog import MainCog
from yt_dl_bot.cogs.systemcog import SystemCog
from yt_dl_bot.cogs.twitchcog import TwitchCog
from yt_dl_bot.cogs.youtubecog import YouTubeCog


class AutomaticRouteErrorReportingTest(unittest.IsolatedAsyncioTestCase):
    def make_route(self, command_name, error):
        bot = Mock()
        bot.command_prefix = "!"
        bot.settings = SimpleNamespace(DOWNLOAD_CHANNEL=10, HIGHLIGHT_CHANNEL=20, LOG_CHANNEL=30)
        bot.services = SimpleNamespace(
            youtube_download=Mock(), youtube_highlight=Mock(), twitch_download=Mock()
        )
        for service in vars(bot.services).values():
            service.check.side_effect = error
            service.create.side_effect = error
        channel = SimpleNamespace(mention="#errors", send=AsyncMock())
        bot.get_channel.return_value = channel
        registry = {}
        for cog in (YouTubeCog(bot), TwitchCog(bot), SystemCog(bot)):
            for command in cog.walk_commands():
                command.cog = cog
                registry[command.qualified_name] = command
        bot.get_command.side_effect = registry.get
        url = (
            "https://www.twitch.tv/channel"
            if command_name == "twitch download"
            else "https://youtu.be/dQw4w9WgXcQ"
        )
        message = Mock(
            content=url,
            author=SimpleNamespace(bot=False),
            channel=SimpleNamespace(id=20 if command_name == "youtube highlight" else 10),
        )
        ctx = commands.Context(message=message, bot=bot, view=StringView(url))
        ctx.reply = AsyncMock()
        bot.get_context = AsyncMock(return_value=ctx)
        return MainCog(bot), message, ctx, channel

    async def test_service_failures_notify_user_and_log_for_all_automatic_routes(self):
        for command_name in ("youtube download", "youtube highlight", "twitch download"):
            with self.subTest(command=command_name):
                error = RuntimeError("service unavailable")
                cog, message, ctx, channel = self.make_route(command_name, error)

                await cog.on_message(message)

                ctx.reply.assert_any_await("Error: Check #errors")
                channel.send.assert_awaited_once()
                ctx.bot.logger.error.assert_called_once()
                self.assertIn("service unavailable", ctx.bot.logger.error.call_args.args[0])
                self.assertTrue(ctx.command_failed)
                self.assertEqual(ctx.command.qualified_name, command_name)
                event, event_ctx, reported = ctx.bot.dispatch.call_args.args
                self.assertEqual(event, "command_error")
                self.assertIs(event_ctx, ctx)
                self.assertIsInstance(reported, commands.CommandInvokeError)
                self.assertIs(reported.original, error)

    async def test_command_errors_are_not_wrapped_again(self):
        error = commands.CommandError("command failed")
        cog, message, ctx, channel = self.make_route("youtube download", error)

        await cog.on_message(message)

        self.assertIs(ctx.bot.dispatch.call_args.args[2], error)
        ctx.reply.assert_awaited_once_with("Error: Check #errors")
        channel.send.assert_awaited_once()

    async def test_download_failure_after_initial_reply_notifies_user(self):
        error = RuntimeError("download failed")
        cog, message, ctx, channel = self.make_route("youtube download", error)
        service = ctx.bot.services.youtube_download
        service.check.side_effect = None
        service.check.return_value = "Starting download"
        service.download.side_effect = error

        await cog.on_message(message)

        self.assertEqual(
            [call.args[0] for call in ctx.reply.await_args_list],
            ["Starting download", "Error: Check #errors"],
        )
        channel.send.assert_awaited_once()
        self.assertIs(ctx.bot.dispatch.call_args.args[2].original, error)

    async def test_cancellation_propagates_without_error_notification(self):
        cog, message, ctx, channel = self.make_route("youtube download", asyncio.CancelledError())

        with self.assertRaises(asyncio.CancelledError):
            await cog.on_message(message)

        ctx.reply.assert_not_awaited()
        channel.send.assert_not_awaited()
        ctx.bot.dispatch.assert_not_called()
        ctx.bot.logger.error.assert_not_called()

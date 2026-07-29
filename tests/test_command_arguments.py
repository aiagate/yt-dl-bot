import unittest
from unittest.mock import AsyncMock, Mock

from discord.ext import commands

from yt_dl_bot.cogs.command_arguments import TwitchURL, YouTubeURL
from yt_dl_bot.cogs.twitchcog import TwitchCog
from yt_dl_bot.cogs.youtubecog import YouTubeCog


class URLConverterTest(unittest.IsolatedAsyncioTestCase):
    async def test_youtube_converter_returns_valid_url(self):
        converted = await YouTubeURL().convert(
            Mock(),
            " https://youtu.be/video ",
        )

        self.assertEqual(converted, "https://youtu.be/video")

    async def test_youtube_converter_rejects_invalid_url(self):
        with self.assertRaisesRegex(
            commands.BadArgument,
            "Invalid youtube URL",
        ):
            await YouTubeURL().convert(
                Mock(),
                "https://www.twitch.tv/channel",
            )

    async def test_twitch_converter_rejects_invalid_url(self):
        with self.assertRaisesRegex(
            commands.BadArgument,
            "Invalid twitch URL",
        ):
            await TwitchURL().convert(
                Mock(),
                "not a URL",
            )


class CommandArgumentDefinitionTest(unittest.TestCase):
    def test_download_commands_require_one_url_and_reject_extras(self):
        commands_to_check = (
            YouTubeCog.download_video,
            YouTubeCog.get_highlight,
            TwitchCog.download_video,
        )

        for command in commands_to_check:
            with self.subTest(command=command.qualified_name):
                self.assertEqual(tuple(command.clean_params), ("url",))
                self.assertFalse(command.ignore_extra)

    def test_url_parameter_uses_service_specific_converter(self):
        self.assertIs(
            YouTubeCog.download_video.clean_params["url"].annotation,
            YouTubeURL,
        )
        self.assertIs(
            YouTubeCog.get_highlight.clean_params["url"].annotation,
            YouTubeURL,
        )
        self.assertIs(
            TwitchCog.download_video.clean_params["url"].annotation,
            TwitchURL,
        )


class CommandArgumentErrorTest(unittest.IsolatedAsyncioTestCase):
    def make_cog(self, cog_type):
        bot = Mock()
        bot.settings = Mock()
        bot.services = Mock()
        bot.get_command.side_effect = lambda name: name
        return cog_type(bot)

    async def assert_user_error(self, cog, handler, error, expected):
        ctx = Mock()
        ctx.reply = AsyncMock()
        ctx.invoke = AsyncMock()

        await handler(cog, ctx, error)

        ctx.reply.assert_awaited_once_with(expected)
        ctx.invoke.assert_not_awaited()

    async def test_missing_url_gets_usage_reply(self):
        parameter = YouTubeCog.download_video.clean_params["url"]
        await self.assert_user_error(
            self.make_cog(YouTubeCog),
            YouTubeCog.download_video_error,
            commands.MissingRequiredArgument(parameter),
            "Error: URL is required. Usage: youtube download <url>",
        )

    async def test_extra_argument_gets_usage_reply(self):
        await self.assert_user_error(
            self.make_cog(TwitchCog),
            TwitchCog.download_video_error,
            commands.TooManyArguments("Too many arguments passed"),
            "Error: too many arguments. Usage: twitch download <url>",
        )

    async def test_invalid_url_gets_clear_reply(self):
        await self.assert_user_error(
            self.make_cog(YouTubeCog),
            YouTubeCog.get_highlight_error,
            commands.BadArgument("Invalid youtube URL"),
            "Error: Invalid youtube URL",
        )

    async def test_unexpected_error_still_uses_error_log(self):
        cog = self.make_cog(YouTubeCog)
        ctx = Mock()
        ctx.reply = AsyncMock()
        ctx.invoke = AsyncMock()
        error = commands.CommandInvokeError(RuntimeError("failed"))

        await YouTubeCog.download_video_error(cog, ctx, error)

        ctx.reply.assert_not_awaited()
        ctx.invoke.assert_awaited_once_with("send_error_log", error)


class AutomaticRouteTest(unittest.IsolatedAsyncioTestCase):
    async def test_direct_invoke_still_accepts_routed_string_url(self):
        bot = Mock()
        bot.settings = Mock()
        bot.services.youtube_download.check.return_value = "ready"
        result = Mock()
        result.info = {"id": "video"}
        result.url = "https://youtu.be/video"
        bot.services.youtube_download.download.return_value = result
        bot.get_command.side_effect = lambda name: name
        ctx = Mock()
        ctx.reply = AsyncMock()
        ctx.invoke = AsyncMock()
        cog = YouTubeCog(bot)

        async def run(function, *args, **kwargs):
            return function(*args, **kwargs)

        with unittest.mock.patch(
            "asyncio.to_thread",
            AsyncMock(side_effect=run),
        ):
            await YouTubeCog.download_video.callback(
                cog,
                ctx,
                "https://youtu.be/video",
            )

        bot.services.youtube_download.check.assert_called_once_with(
            "https://youtu.be/video",
        )

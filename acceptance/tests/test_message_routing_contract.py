"""Acceptance tests for acceptance/contracts/message-routing.md."""

import unittest

from acceptance.support.message_routing import RoutingDecision, route_message


class MessageRoutingContractTest(unittest.TestCase):
    def test_routes_a_youtube_url_to_the_download_channel(self) -> None:
        # Contract: supported YouTube URLs download in the download channel.
        url = "https://youtu.be/dQw4w9WgXcQ"

        self.assertEqual(
            route_message(author_is_bot=False, content=url, channel_id=10),
            RoutingDecision(action="youtube download", url=url),
        )

    def test_routes_a_youtube_url_to_the_highlight_channel(self) -> None:
        # Contract: supported YouTube URLs create highlights in that channel.
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        self.assertEqual(
            route_message(author_is_bot=False, content=url, channel_id=20),
            RoutingDecision(action="youtube highlight", url=url),
        )

    def test_ignores_a_twitch_url_in_the_highlight_channel(self) -> None:
        # Contract: Twitch URLs are not routed by the highlight channel.
        self.assertEqual(
            route_message(
                author_is_bot=False,
                content="https://www.twitch.tv/example_channel",
                channel_id=20,
            ),
            RoutingDecision(action="ignore", url=None),
        )

    def test_trims_a_url_before_routing_it(self) -> None:
        # Contract: surrounding whitespace is accepted and removed.
        url = "https://www.twitch.tv/example_channel"

        self.assertEqual(
            route_message(author_is_bot=False, content=f"  {url}  ", channel_id=10),
            RoutingDecision(action="twitch download", url=url),
        )

    def test_ignores_bot_messages_even_when_they_contain_a_valid_url(self) -> None:
        # Contract: messages from bots are ignored.
        self.assertEqual(
            route_message(
                author_is_bot=True,
                content="https://youtu.be/dQw4w9WgXcQ",
                channel_id=10,
            ),
            RoutingDecision(action="ignore", url=None),
        )

    def test_classifies_a_command_before_considering_media_urls(self) -> None:
        # Contract: a command-prefixed message is classified as a command,
        # even when its text also contains a supported media URL.
        decision = route_message(
            author_is_bot=False,
            content="!clip https://youtu.be/dQw4w9WgXcQ",
            channel_id=10,
        )

        self.assertEqual(decision.action, "command")

    def test_ignores_non_text_message_content(self) -> None:
        # Contract: message content that is not text is ignored.
        self.assertEqual(
            route_message(author_is_bot=False, content=None, channel_id=10),
            RoutingDecision(action="ignore", url=None),
        )

    def test_ignores_a_supported_url_in_an_unrelated_channel(self) -> None:
        # Contract: supported URLs are ignored outside the configured channels.
        self.assertEqual(
            route_message(
                author_is_bot=False,
                content="https://youtu.be/dQw4w9WgXcQ",
                channel_id=999,
            ),
            RoutingDecision(action="ignore", url=None),
        )

    def test_ignores_a_supported_url_when_surrounded_by_prose(self) -> None:
        # Contract: only a message containing the URL itself is routable.
        self.assertEqual(
            route_message(
                author_is_bot=False,
                content="Watch this https://youtu.be/dQw4w9WgXcQ",
                channel_id=10,
            ),
            RoutingDecision(action="ignore", url=None),
        )

    def test_ignores_an_unsupported_url(self) -> None:
        # Contract: unsupported URLs are ignored.
        self.assertEqual(
            route_message(
                author_is_bot=False,
                content="https://vimeo.com/123456",
                channel_id=10,
            ),
            RoutingDecision(action="ignore", url=None),
        )

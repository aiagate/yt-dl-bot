# Discord message routing contract

This contract describes the observable routing decision made for one incoming
Discord message. It deliberately does not describe the application's internal
classes or collaborators.

## Test interface

Use `acceptance.support.message_routing.route_message`. It accepts:

| Argument | Meaning |
| --- | --- |
| `author_is_bot` | Whether the author is a bot. |
| `content` | The raw message content. It may be any Python object. |
| `channel_id` | The channel that received the message. |
| `download_channel` | Channel configured for downloads; defaults to `10`. |
| `highlight_channel` | Channel configured for highlights; defaults to `20`. |
| `command_prefix` | Command prefix or prefixes; defaults to `!`. |

It returns a `RoutingDecision` with `action` and `url` fields. The possible
action strings are `ignore`, `command`, `youtube download`,
`youtube highlight`, and `twitch download`.

## Required behaviour

- Messages from bots, and message content that is not text, are ignored.
- A message beginning with a configured command prefix is classified as a
  `command`; it is not automatically routed as a media URL.
- A message containing only a supported HTTP(S) YouTube URL is routed to
  `youtube download` in the download channel and `youtube highlight` in the
  highlight channel.
- A message containing only a supported HTTP(S) Twitch URL is routed to
  `twitch download` in the download channel. Twitch URLs are ignored in the
  highlight channel.
- Leading and trailing whitespace around a supported URL is accepted. The
  returned URL has that surrounding whitespace removed.
- A URL with surrounding prose, an unsupported URL, or a supported URL in an
  unrelated channel is ignored.

The contract does not require network access.

# yt-dl-bot

## Development environment

Install [uv](https://docs.astral.sh/uv/) and create the locked Python 3.12
environment:

```sh
uv sync --locked
```

Add or update dependencies through `uv add` and `uv lock`. Commit both
`pyproject.toml` and `uv.lock`.

Run the installed package from any working directory:

```sh
uv run yt-dl-bot
# Equivalent module entry point:
uv run python -m yt_dl_bot.discord_bot_main
```

## Configuration

Copy the environment template and replace every placeholder and channel ID:

```sh
cp .env.example .env
```

The local `.env` file is ignored by Git. Keep the Discord credential there and
never commit it.

The bot reads ordinary prefixed commands and routes supported URLs from message
text, so **Message Content Intent** must be enabled under **Bot > Privileged
Gateway Intents** in the Discord Developer Portal. No other privileged gateway
intent is required.

Complete exception tracebacks are written to the configured local log. Reports
sent to the Discord log channel redact common structured credentials (including
authorization and cookie headers, secret-like key/value pairs, URL user
information and sensitive query parameters) and local absolute paths. This
redaction reduces accidental disclosure but cannot recognize every arbitrary
secret embedded in free-form exception text; avoid including credentials in
exception messages.

Runtime data paths default to repository-local directories. When running the
Python application directly, override them with `SAVE_PATH`, `TMP_PATH`,
`GRAPH_SAVE_PATH`, or `LOG_PATH`. In Compose, `DOWNLOADS_PATH` and `COOKIE_PATH`
select the host directories mounted at `/app/downloads` and `/app/cookie`;
application paths inside the container remain unchanged. Twitch downloads use
`cookie/cookies.txt` when that file exists.

## Architecture

The bot keeps Discord handling separate from download and chat processing:

```text
Discord message
  -> MainCog / MessageRouter
  -> YouTubeCog or TwitchCog
  -> application service
  -> YouTubeDownloader or YtDlpDownloader
  -> shared DownloadEngine
  -> yt-dlp and the filesystem
```

`ApplicationServices.from_settings()` creates the services used by the Cogs.
The application services translate extractor, chat, and filesystem failures
into application errors. `DownloadEngine` orchestrates the shared yt-dlp
workflow, `DownloadPolicy` provides site-specific behavior, and `ArtifactStore`
owns destination planning, collision checks, moves, and rollback. YouTube
highlight creation follows a separate
`YouTubeHighlightService -> ChatHighlightPipeline -> PytchatSource / HighlightAnalyzer
/ MatplotlibGraphRenderer` path.

The main implementation areas are:

- `cogs/`: Discord commands, replies, embeds, and automatic message routing.
- `application_container.py`: composition root that wires adapters into services.
- `application_results.py`: Discord-independent use-case result objects.
- `cogs/highlight_presenter.py`: Discord embed and field-limit formatting for
  structured highlight results.
- `video_download_service.py`: video check and download use cases.
- `youtube_highlight_service.py`: YouTube highlight creation and graph archival.
- `download_engine.py`: yt-dlp options, retry behavior, and download orchestration.
- `artifact_store.py`: final artifact layout, collision checks, moves, and rollback.
- `chat_highlights.py`: replay-chat collection, peak detection, and graph
  rendering.
- `setting.py`: environment-backed runtime settings and the initial Cog list.

### Commands and automatic routing

The command prefix is `!`. User-facing media commands are:

```text
!youtube download <url>
!youtube highlight <url>
!twitch download <url>
```

Messages containing only a supported HTTP(S) URL are routed automatically:

| Channel setting | YouTube URL | Twitch URL |
| --- | --- | --- |
| `DOWNLOAD_CHANNEL` | `youtube download` | `twitch download` |
| `HIGHLIGHT_CHANNEL` | `youtube highlight` | ignored |

Leading and trailing whitespace is accepted, but surrounding prose is not. Bot
messages, unsupported hosts, unsupported channels, and normal `!` commands are
left alone.

Owner-only administration commands are `!system close`, `!cog load <name>`,
`!cog reload <name>`, and `!cog unload <name>`. Cog commands accept `all`;
unloading all Cogs or `systemcog` additionally requires `-f`.

### YouTube and Twitch behavior

Both download paths use the shared engine and move completed artifacts out of
the cache. Their policies differ:

- YouTube retries recognized scheduled/live conditions, starts live downloads
  from the beginning, and requires both metadata and thumbnail artifacts.
- Twitch uses the generic yt-dlp policy without scheduled retries or
  `live_from_start`. It reports an offline stream separately and uses
  `cookie/cookies.txt` when present; metadata and thumbnail artifacts are
  optional.
- Highlight creation is YouTube-only. It reads replay chat, identifies activity
  peaks in 30-second buckets, posts the links and graph, then archives the graph.

### Artifact layout

With the default settings, yt-dlp writes temporary files under
`downloads/cache/` and successful processing produces:

```text
downloads/
├── <timestamp>_<video-id>.<video-extension>
├── metadata/
│   └── <timestamp>_<video-id>.<metadata-extension>
├── thumbnail/
│   └── <timestamp>_<video-id>.<image-extension>
└── graph/
    └── scoregraph_<timestamp>_<video-id>.png
```

The video is stored directly under `SAVE_PATH`. Metadata and thumbnails are
stored in its `metadata/` and `thumbnail/` children. Highlight graphs are
created under `TMP_PATH` and moved to `GRAPH_SAVE_PATH` after they are posted.

### Extending the bot

To add a Cog, create a module under `src/yt_dl_bot/cogs/` with an async
`setup(bot)` function, register commands or listeners on a `commands.Cog`, and
add its import path to `DEFAULT_INITIAL_EXTENSIONS` in `setting.py`. Obtain
configuration from `bot.settings` and shared use cases from `bot.services`
instead of constructing them inside command handlers.

To add a download source, first add strict URL identification/validation in
`url_validation.py`. Reuse `DownloadEngine` with a suitable `DownloadPolicy`
when the yt-dlp workflow applies, wrap it in an application service that exposes
stable result types and application errors, add that service to
`ApplicationServices`, and keep Discord presentation in a dedicated Cog.
Dependency-bearing logic should accept collaborators explicitly so tests can
replace network, clock, sleep, and filesystem behavior.

## Compose

Validate the configuration before starting services:

```sh
docker compose config --quiet
docker compose up -d
```

The Compose configuration runs the bot without an external database.

## Tests

```sh
uv run ruff format --check src tests scripts
uv run ruff check src tests scripts
uv run mypy
uv run coverage run -m unittest discover -s tests -v
uv run coverage report
uv run pip-audit
uv lock --check
docker compose --env-file .env.example config --quiet
```

CI enforces Ruff formatting and linting across `src/`, `tests/`, and `scripts/`, type
checking of every module under `src/yt_dl_bot`, and at least 85% branch
coverage. Run `uv run ruff format src tests scripts` to apply formatting locally.

### External integration smoke tests

The non-required **External integration smoke** workflow runs every Monday at
04:17 UTC and can also be started from the Actions tab with **Run workflow**.
It probes three boundaries independently:

- yt-dlp metadata extraction without downloading media;
- the first batch of an archived YouTube chat replay through pytchat;
- local ffmpeg/ffprobe execution and metadata postprocessing using a one-second
  synthetic audio source.

Each job has bounded retries and a five-minute process timeout. Reports are
written to the GitHub step summary and retained as JSON artifacts for 14 days.
Failures do not block pull requests because upstream availability, geo/rate
limits, removed videos, and YouTube response changes can make these checks
occasionally flaky. Re-run once before treating a failure as integration drift.

The defaults are public test/replay videos and use no credentials. Repository
variables `YTDLP_SMOKE_URL` and `PYTCHAT_SMOKE_VIDEO_ID` override them for
scheduled runs; manual dispatch inputs take precedence over repository
variables. Override targets must remain publicly accessible; this workflow
never downloads full media.

Run the deterministic ffmpeg probe locally with:

```sh
uv run python scripts/external_smoke.py ffmpeg
```

The validation helpers are covered by ordinary offline unit tests. The yt-dlp
and pytchat probes intentionally run only in the separate scheduled/manual
workflow, so regular CI does not depend on external media services.

The mypy configuration requires complete annotations on every function,
typed generic arguments and decorators, explicit optional types, type-safe
returns, strict equality checks, reachable code, and actively used
configuration sections. Values read from untyped third-party APIs remain
`object` at their input boundary until runtime validation narrows them. The
narrowly scoped third-party missing-import overrides and discord.py decorator
ignores are documented next to their configuration or call sites.

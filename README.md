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

Runtime data paths default to repository-local directories and can be changed
with `DOWNLOADS_PATH` and `COOKIE_PATH`.

## Compose

Validate the configuration before starting services:

```sh
docker compose config --quiet
docker compose up -d
```

The Compose configuration runs the bot without an external database.

## Tests

```sh
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy
uv run coverage run -m unittest discover -s tests -v
uv run coverage report
uv run pip-audit
uv lock --check
docker compose --env-file .env.example config --quiet
```

CI enforces Ruff formatting and linting across `src/` and `tests/`,
incremental type checking of the core boundary and pure-logic modules, and at
least 70% branch coverage. Run `uv run ruff format src tests` to apply
formatting locally.

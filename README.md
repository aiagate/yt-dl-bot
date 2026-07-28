# yt-dl-bot

## Development environment

Install [uv](https://docs.astral.sh/uv/) and create the locked Python 3.12
environment:

```sh
uv sync --locked
```

Add or update dependencies through `uv add` and `uv lock`. Commit both
`pyproject.toml` and `uv.lock`.

## Configuration

Copy the environment template and replace every placeholder and channel ID:

```sh
cp .env.example .env
```

The local `.env` file is ignored by Git. Keep Discord, YouTube, and database
credentials there and never commit them.

Runtime data paths default to repository-local directories and can be changed
with `DOWNLOADS_PATH`, `DATABASES_PATH`, and `COOKIE_PATH`.

## Compose

Validate the configuration before starting services:

```sh
docker compose config --quiet
docker compose up -d
```

MySQL data is stored in the named `mysql-data` volume. The bot waits for the
database healthcheck before starting.

## Tests

```sh
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q source tests
uv run pip-audit
uv lock --check
docker compose --env-file .env.example config --quiet
```

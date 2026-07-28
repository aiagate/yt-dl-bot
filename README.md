# yt-dl-bot

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

## Known build prerequisite

The legacy chat feature currently requires `dist/pytchat-0.5.6.tar.gz` during
the image build. This dependency is intentionally retained until that feature
is removed.

## Tests

```sh
python -m unittest discover -s tests -v
python -m compileall -q source tests
docker compose --env-file .env.example config --quiet
```

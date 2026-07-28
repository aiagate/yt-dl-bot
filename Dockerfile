FROM ghcr.io/astral-sh/uv:0.11.29 AS uv

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY ./src/ ./src/
RUN uv sync --locked --no-dev --no-cache

CMD ["/app/.venv/bin/python", "-m", "yt_dl_bot.discord_bot_main"]

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY ./source/requirements.txt ./requirements.txt
COPY ./dist/* ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir pytchat-0.5.6.tar.gz

COPY ./source/ ./

CMD ["python3", "discord_bot_main.py"]

#!/usr/bin/env python3
"""Small, bounded probes for integrations that unit tests cannot exercise."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

DEFAULT_YTDLP_URL = "https://www.w3schools.com/html/mov_bbb.mp4"
DEFAULT_PYTCHAT_VIDEO_ID = "1xO3eP5HVhg"


class SmokeFailure(RuntimeError):
    """A stage-specific, actionable smoke-test failure."""


def require_metadata(info: object, expected_id: str | None = None) -> dict[str, object]:
    if not isinstance(info, dict):
        raise SmokeFailure("yt-dlp returned a non-object metadata result")
    missing = [key for key in ("id", "title", "formats") if not info.get(key)]
    if missing:
        raise SmokeFailure(f"yt-dlp metadata is missing required fields: {', '.join(missing)}")
    if expected_id and info["id"] != expected_id:
        raise SmokeFailure(f"yt-dlp returned id {info['id']!r}, expected {expected_id!r}")
    formats = info["formats"]
    if not isinstance(formats, list) or not formats:
        raise SmokeFailure("yt-dlp metadata contains no downloadable formats")
    return info


def require_chat_batch(is_replay: object, items: object) -> int:
    if is_replay is not True:
        raise SmokeFailure("pytchat did not identify the target as an archived chat replay")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)) or not items:
        raise SmokeFailure("pytchat returned an empty first replay batch")
    return len(items)


def require_ffprobe(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise SmokeFailure("ffprobe returned a non-object result")
    streams = payload.get("streams")
    if not isinstance(streams, list) or not streams:
        raise SmokeFailure("ffprobe found no streams in the postprocessed file")
    format_data = payload.get("format")
    if not isinstance(format_data, dict):
        raise SmokeFailure("ffprobe returned no format metadata")
    tags = format_data.get("tags")
    if not isinstance(tags, dict) or tags.get("title") != "yt-dl-bot smoke":
        raise SmokeFailure("ffmpeg did not preserve the expected postprocessing metadata")
    return payload


def retry(
    operation: Callable[[], dict[str, object]], attempts: int, delay_seconds: float
) -> dict[str, object]:
    failures: list[str] = []
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:
            failures.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
            if attempt < attempts:
                time.sleep(delay_seconds)
    raise SmokeFailure("; ".join(failures))


def smoke_ytdlp(url: str, attempts: int) -> dict[str, object]:
    import yt_dlp

    expected_id = url.split("v=", 1)[1].split("&", 1)[0] if "v=" in url else None

    def extract() -> dict[str, object]:
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 20,
            "extract_flat": False,
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            return require_metadata(ydl.extract_info(url, download=False), expected_id)

    info = retry(extract, attempts, 3)
    return {
        "stage": "yt-dlp metadata",
        "target": url,
        "video_id": info["id"],
        "format_count": len(info["formats"]),  # type: ignore[arg-type]
    }


def smoke_pytchat(video_id: str, attempts: int) -> dict[str, object]:
    import pytchat

    def fetch() -> dict[str, object]:
        chat: Any = None
        try:
            chat = pytchat.create(video_id=video_id, force_replay=True)
            items = list(chat.get().sync_items())
            count = require_chat_batch(chat.is_replay(), items)
            return {"message_count": count}
        finally:
            if chat is not None:
                chat.terminate()

    result = retry(fetch, attempts, 3)
    return {
        "stage": "pytchat replay",
        "target": video_id,
        "message_count": result["message_count"],
    }


def smoke_ffmpeg() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="yt-dl-bot-smoke-") as directory:
        output = Path(directory) / "postprocessed.m4a"
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=1",
            "-metadata",
            "title=yt-dl-bot smoke",
            "-c:a",
            "aac",
            "-y",
            str(output),
        ]
        subprocess.run(command, check=True, timeout=20)
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        require_ffprobe(json.loads(probe.stdout))
        return {"stage": "ffmpeg postprocessing", "bytes": output.stat().st_size}


def write_report(stage: str, report: dict[str, object], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{stage}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as summary:
            summary.write(f"### External smoke: {stage}\n\n")
            summary.write("```json\n")
            summary.write(json.dumps(report, indent=2, ensure_ascii=False))
            summary.write("\n```\n")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("yt-dlp", "pytchat", "ffmpeg"))
    parser.add_argument("--yt-dlp-url", default=DEFAULT_YTDLP_URL)
    parser.add_argument("--pytchat-video-id", default=DEFAULT_PYTCHAT_VIDEO_ID)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--output-dir", type=Path, default=Path("smoke-results"))
    args = parser.parse_args(argv)
    if args.attempts < 1 or args.attempts > 3:
        parser.error("--attempts must be between 1 and 3")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.stage == "yt-dlp":
            report = smoke_ytdlp(args.yt_dlp_url, args.attempts)
        elif args.stage == "pytchat":
            report = smoke_pytchat(args.pytchat_video_id, args.attempts)
        else:
            report = smoke_ffmpeg()
        report["status"] = "passed"
        write_report(args.stage, report, args.output_dir)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except Exception as exc:
        report = {
            "stage": args.stage,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }
        write_report(args.stage, report, args.output_dir)
        print(f"external smoke stage {args.stage!r} failed: {report['error']}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

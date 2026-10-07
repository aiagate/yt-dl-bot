#!/usr/bin/env python3
"""Small, bounded probes for integrations that unit tests cannot exercise."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DEFAULT_YTDLP_URL = "https://www.w3schools.com/html/mov_bbb.mp4"
DEFAULT_PYTCHAT_VIDEO_ID = "4xnApfWvjXs"
CHANNEL_DIAGNOSTIC_BODY_LIMIT = 4 * 1024 * 1024


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
            batch = chat.get()
            chat.raise_for_status()
            count = require_chat_batch(chat.is_replay(), batch.items)
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


def diagnose_pytchat_channel(video_id: str) -> dict[str, object]:
    """Observe public parser inputs without publishing response or credential values."""
    import httpx
    from pytchat import config, util

    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise SmokeFailure("channel diagnostic requires an 11-character public video ID")

    def strip_credentials(request: httpx.Request) -> None:
        for name in ("cookie", "authorization", "proxy-authorization"):
            request.headers.pop(name, None)

    responses: list[dict[str, object]] = []
    report: dict[str, object] = {
        "stage": "pytchat channel diagnostic",
        "responses": responses,
        "request_limit": 2,
        "body_prefix_limit_bytes": CHANNEL_DIAGNOSTIC_BODY_LIMIT,
        "deadline_target_seconds": 20,
        "socket_timeout_seconds": 8,
        "accept_encoding_identity": True,
        "follows_redirects": False,
        "uses_environment_proxy": False,
        "environment_proxy_configured": any(
            os.environ.get(name)
            for name in (
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "ALL_PROXY",
                "http_proxy",
                "https_proxy",
                "all_proxy",
            )
        ),
    }
    deadline = time.monotonic() + 20
    endpoints = (
        (
            "embed",
            f"https://www.youtube.com/embed/{video_id}",
            config.headers,
            util.PATTERN_CHANNEL,
        ),
        (
            "mobile",
            f"https://m.youtube.com/watch?v={video_id}",
            config.m_headers,
            util.PATTERN_M_CHANNEL,
        ),
    )
    with httpx.Client(
        http2=True,
        timeout=8,
        follow_redirects=False,
        auth=None,
        trust_env=False,
        event_hooks={"request": [strip_credentials]},
    ) as client:
        for endpoint, url, headers, pattern in endpoints:
            if time.monotonic() >= deadline:
                report["outcome"] = "deadline_exceeded"
                break
            response_report: dict[str, object] = {"endpoint": endpoint}
            responses.append(response_report)
            try:
                with client.stream(
                    "GET", url, headers={**headers, "accept-encoding": "identity"}
                ) as response:
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                    location = urlsplit(response.headers.get("location", ""))
                    consent_redirect = location.hostname in (
                        "consent.youtube.com",
                        "consent.google.com",
                    )
                    login_redirect = location.hostname == "accounts.google.com"
                    response_report.update(
                        http_status=response.status_code,
                        content_type=content_type
                        if content_type in ("text/html", "application/json", "text/plain", "")
                        else "other",
                        redirects=300 <= response.status_code < 400,
                        redirects_to_desktop_watch=location.hostname == "www.youtube.com"
                        and location.path == "/watch",
                        consent_redirect=consent_redirect,
                        login_redirect=login_redirect,
                        access_stop=False,
                        body_bytes_received=0,
                        body_bytes_retained=0,
                        body_inspected=False,
                        body_complete=False,
                    )
                    if (
                        response.status_code in (401, 403, 429)
                        or consent_redirect
                        or login_redirect
                    ):
                        response_report["access_stop"] = True
                        report["outcome"] = "access_stop"
                        break
                    if response.status_code >= 400:
                        report["outcome"] = "http_error"
                        break
                    if response.headers.get("content-encoding", "").lower() not in ("", "identity"):
                        response_report["unexpected_content_encoding"] = True
                        report["outcome"] = "encoded_response_not_inspected"
                        break
                    if time.monotonic() >= deadline:
                        response_report["request_error"] = "deadline_exceeded"
                        report["outcome"] = "deadline_exceeded"
                        break
                    body = bytearray()
                    complete = True
                    response_report["body_inspected"] = True
                    for chunk in response.iter_raw():
                        response_report["body_bytes_received"] += len(chunk)
                        if time.monotonic() >= deadline:
                            response_report["request_error"] = "deadline_exceeded"
                            complete = False
                            break
                        remaining = CHANNEL_DIAGNOSTIC_BODY_LIMIT - len(body)
                        body.extend(chunk[:remaining])
                        response_report["body_bytes_retained"] = len(body)
                        if len(body) >= CHANNEL_DIAGNOSTIC_BODY_LIMIT:
                            response_report["body_limit_hit"] = True
                            complete = False
                            break
                    text = body.decode("utf-8", errors="replace")
                    normalized = text.replace("\\", "").lower()
                    features = {
                        "unusual_traffic": "our systems have detected unusual traffic"
                        in normalized,
                        "captcha": "g-recaptcha" in normalized or 'id="captcha"' in normalized,
                        "bot_confirmation": bool(
                            re.search(r"sign in to confirm you(?:'|\u2019)re not a bot", normalized)
                        ),
                        "login_required": bool(
                            re.search(r'"status"\s*:\s*"login_required"', normalized)
                        ),
                    }
                    access_stop = (
                        response.status_code in (401, 403, 429)
                        or any(features.values())
                        or consent_redirect
                        or login_redirect
                    )
                    response_report.update(
                        body_complete=complete,
                        pytchat_pattern_match=bool(pattern.search(text)),
                        plain_channel_id_match=bool(
                            re.search(r'"channelId"\s*:\s*"UC[A-Za-z0-9_-]{22}"', text)
                        ),
                        channel_id_key_present="channelId" in text,
                        player_response_present="ytInitialPlayerResponse" in text,
                        refusal_features=features,
                        access_stop=access_stop,
                    )
                    if access_stop:
                        report["outcome"] = "access_stop"
                        break
                    if not complete or response.status_code >= 400:
                        report["outcome"] = "incomplete_or_http_error"
                        break
                    if response_report["pytchat_pattern_match"]:
                        report["outcome"] = "channel_pattern_found"
                        break
                    if endpoint == "mobile":
                        report["outcome"] = (
                            "redirect_not_followed"
                            if response_report["redirects"]
                            else "channel_pattern_absent"
                        )
            except Exception as exc:
                response_report["request_error"] = (
                    "timeout"
                    if isinstance(exc, httpx.TimeoutException)
                    else "transport_error"
                    if isinstance(exc, httpx.TransportError)
                    else "unexpected_error"
                )
                report["outcome"] = "request_failed"
                break
    return report


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
    parser.add_argument("stage", choices=("yt-dlp", "pytchat", "pytchat-channel", "ffmpeg"))
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
        elif args.stage == "pytchat-channel":
            report = diagnose_pytchat_channel(args.pytchat_video_id)
        else:
            report = smoke_ffmpeg()
        report["status"] = "observed" if args.stage == "pytchat-channel" else "passed"
        write_report(args.stage, report, args.output_dir)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except Exception as exc:
        report = {
            "stage": args.stage,
            "status": "failed",
            "error": type(exc).__name__
            if args.stage == "pytchat-channel"
            else f"{type(exc).__name__}: {exc}",
        }
        write_report(args.stage, report, args.output_dir)
        print(f"external smoke stage {args.stage!r} failed: {report['error']}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

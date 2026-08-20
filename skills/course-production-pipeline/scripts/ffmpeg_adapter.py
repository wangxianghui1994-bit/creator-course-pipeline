#!/usr/bin/env python3
"""Small, local FFmpeg adapter used by the public demo and as a template."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _filter_path(path: Path) -> str:
    value = path.resolve().as_posix()
    return value.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def render(job: dict[str, Any]) -> Path:
    source = Path(job["source_video"])
    subtitles = Path(job["subtitles"])
    output = Path(job["output"])
    width = int(job.get("width", 1920))
    height = int(job.get("height", 1080))
    start = float(job.get("start_seconds", 0))
    duration = float(job["duration_seconds"])
    if width <= 0 or height <= 0 or start < 0 or duration <= 0:
        raise ValueError("invalid dimensions or timing")
    output.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        f"subtitles='{_filter_path(subtitles)}'"
    )
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", str(start), "-i", str(source), "-t", str(duration),
        "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"ffmpeg render failed: {completed.stderr[-1200:]}")
    return output

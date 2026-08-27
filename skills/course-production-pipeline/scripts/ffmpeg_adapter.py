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
    background_audio = job.get("background_audio")
    background_gain = float(job.get("background_gain", 0.08))
    if width <= 0 or height <= 0 or start < 0 or duration <= 0:
        raise ValueError("invalid dimensions or timing")
    if background_audio and not 0 < background_gain <= 1:
        raise ValueError("background_gain must be greater than 0 and no greater than 1")
    output.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        f"subtitles='{_filter_path(subtitles)}'"
    )
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start), "-i", str(source)]
    if background_audio:
        command.extend([
            "-stream_loop", "-1", "-i", str(background_audio),
            "-filter_complex", f"[0:a]aresample=48000[narration];[1:a]volume={background_gain:.4f},aresample=48000[background];[narration][background]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[mixed]",
            "-map", "0:v:0", "-map", "[mixed]",
        ])
    else:
        command.extend(["-map", "0:v:0", "-map", "0:a:0"])
    command.extend([
        "-t", str(duration), "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(output),
    ])
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"ffmpeg render failed: {completed.stderr[-1200:]}")
    return output

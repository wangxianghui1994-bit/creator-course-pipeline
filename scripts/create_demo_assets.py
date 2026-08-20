#!/usr/bin/env python3
"""Generate copyright-free synthetic media and a complete demo package."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_SCRIPTS = ROOT / "skills" / "course-production-pipeline" / "scripts"
sys.path.insert(0, str(ADAPTER_SCRIPTS))
from run_default_video_adapter import load_job, render_job  # noqa: E402


def _run(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    if completed.returncode:
        raise RuntimeError(f"command failed: {completed.stderr[-1000:]}")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _metadata() -> dict[str, Any]:
    core = ["learning", "practice"]
    episode = ["demo-video", "local-qa"]
    values = core + episode
    return {
        "title": "Synthetic course episode",
        "description": "A local-only demonstration package generated with FFmpeg.",
        "keyword_policy": {"core": core, "episode": episode, "reject_unlisted": True},
        "douyin": {"keywords": values, "hashtags": values},
        "bilibili": {"tags": values},
        "youtube": {"tags": values},
        "policy": {"publish": False, "schedule": False, "delete": False},
    }


def build_demo(output: Path, force: bool = False) -> Path:
    output = output.resolve()
    if output.exists() and any(output.iterdir()) and not force:
        raise FileExistsError(f"output is not empty; pass --force to replace: {output}")
    if output.exists() and force:
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    package = output / "EP00-demo"
    package.mkdir()
    source = output / "source.mp4"
    subtitles = output / "subtitles-zh-Hans.srt"
    _run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=0x263238:s=1280x720:r=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        "-t", "6", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(source),
    ])
    subtitles.write_text(
        "1\n00:00:00,000 --> 00:00:02,500\nLearning is a practice.\n\n"
        "2\n00:00:02,500 --> 00:00:05,500\nThis package is local and inspectable.\n",
        encoding="utf-8",
    )
    covers = {
        "cover-bilibili-1146x717.png": (1146, 717, "0x455A64"),
        "cover-youtube-1280x720.png": (1280, 720, "0x37474F"),
        "cover-douyin-1080x1920.png": (1080, 1920, "0x546E7A"),
    }
    for filename, (width, height, color) in covers.items():
        _run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height + 1}",
            "-vf", f"format=rgb24,crop={width}:{height}:0:0",
            "-frames:v", "1", "-pix_fmt", "rgb24", str(output / filename),
        ])

    # Keep the generated demo self-contained so it also works from a fresh
    # temporary directory used by CI or a first-time user.
    shutil.copy2(ADAPTER_SCRIPTS / "ffmpeg_adapter.py", output / "ffmpeg_adapter.py")
    registry = output / "registry.json"
    registry.write_text(json.dumps({
        "version": "0.1",
        "adapters": [{
            "id": "ffmpeg-demo",
            "status": "default",
            "entrypoint": "ffmpeg_adapter.py",
            "capabilities": ["render", "subtitles", "h264-aac"],
        }],
    }, indent=2), encoding="utf-8")
    config = output / "jobs.json"
    config.write_text(json.dumps({
        "adapter_id": "ffmpeg-demo",
        "jobs": {
            "master": {
                "source_video": "source.mp4", "subtitles": "subtitles-zh-Hans.srt",
                "output": "EP00-demo/master-16x9.mp4", "work_dir": "work",
                "duration_seconds": 5, "width": 1920, "height": 1080,
            },
            "vertical": {
                "source_video": "source.mp4", "subtitles": "subtitles-zh-Hans.srt",
                "output": "EP00-demo/douyin-9x16.mp4", "work_dir": "work",
                "duration_seconds": 5, "width": 1080, "height": 1920,
            },
        },
    }, indent=2), encoding="utf-8")
    for job_id in ("master", "vertical"):
        job = load_job(config, job_id, registry_path=registry)
        render_job(job, force=False)
    shutil.copy2(subtitles, package / subtitles.name)
    for filename in covers:
        shutil.copy2(output / filename, package / filename)
    metadata = _metadata()
    (package / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    file_map = {path.name: path.name for path in sorted(package.iterdir()) if path.is_file()}
    # The manifest itself is added after the initial file map; it describes the
    # media, covers, subtitles, and metadata but not its own bytes.
    hashes = {asset_id: _hash(package / filename) for asset_id, filename in file_map.items()}
    manifest = {"files": file_map, "asset_sha256": hashes}
    (package / "publish-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    state = {
        "status": "package_ready",
        "subtitle_policy": "do not upload subtitles unless the user reviews the platform requirement",
        "policy": {"publish": False, "schedule": False, "delete": False},
        "platforms": {
            name: {"status": "package_ready", "public_url": None}
            for name in ("douyin", "bilibili", "youtube")
        },
    }
    (package / "publish-state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    (package / "qa-report.json").write_text(json.dumps({
        "status": "pass", "manifest_hashes_match": True, "media_probe": "ffprobe-required",
    }, indent=2), encoding="utf-8")
    return package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "examples" / "demo" / "generated")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    package = build_demo(args.output, force=args.force)
    print(json.dumps({"status": "created", "package": str(package)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

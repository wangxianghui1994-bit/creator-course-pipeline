#!/usr/bin/env python3
"""Run a registered local video adapter without network or publishing actions."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _resolve_path(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _load_renderer(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("creator_course_adapter", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load adapter module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registry_default(registry_path: Path) -> dict[str, Any]:
    registry = _load_json(registry_path)
    defaults = [entry for entry in registry.get("adapters", []) if entry.get("status") == "default"]
    if len(defaults) != 1:
        raise ValueError(f"registry must contain exactly one default adapter, got {len(defaults)}")
    return defaults[0]


def load_job(
    config_path: Path,
    job_id: str,
    expected_adapter_id: str | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = _load_json(config_path)
    adapter = _registry_default(registry_path.resolve()) if registry_path else None
    expected = (adapter or {}).get("id") or expected_adapter_id or config.get("adapter_id")
    if not expected:
        raise ValueError("adapter id must come from a registry, argument, or config")
    actual = config.get("adapter_id", expected)
    if actual != expected:
        raise ValueError(f"adapter_id mismatch: expected {expected}, got {actual}")

    renderer_value = config.get("renderer_module")
    if not renderer_value and adapter:
        renderer_value = adapter.get("entrypoint")
        for base in (registry_path.parent, registry_path.parent.parent):
            candidate = _resolve_path(str(renderer_value or ""), base)
            if candidate.is_file():
                renderer_value = str(candidate)
                break
    renderer_path = _resolve_path(str(renderer_value or ""), config_path.parent)
    if not renderer_path.is_file():
        raise FileNotFoundError(f"renderer module does not exist: {renderer_path}")
    renderer = _load_renderer(renderer_path)

    jobs = config.get("jobs")
    if not isinstance(jobs, dict) or job_id not in jobs:
        raise KeyError(f"job not found: {job_id}")
    raw_job = jobs[job_id]
    if not isinstance(raw_job, dict):
        raise ValueError(f"job must be an object: {job_id}")
    if not callable(getattr(renderer, "render", None)):
        scene_symbol = str(raw_job.get("scene_symbol", ""))
        if not scene_symbol or not hasattr(renderer, scene_symbol):
            raise ValueError(f"scene_symbol not found in renderer: {scene_symbol}")
        for function_name in ("render_clean", "finish"):
            if not callable(getattr(renderer, function_name, None)):
                raise ValueError(f"renderer is missing callable: {function_name}")

    source_video = _resolve_path(str(raw_job.get("source_video", "")), config_path.parent)
    subtitles = _resolve_path(str(raw_job.get("subtitles", "")), config_path.parent)
    background_audio_value = raw_job.get("background_audio")
    background_audio = None
    if background_audio_value:
        background_audio = _resolve_path(str(background_audio_value), config_path.parent)
    if not source_video.is_file():
        raise FileNotFoundError(f"source_video does not exist: {source_video}")
    if not subtitles.is_file():
        raise FileNotFoundError(f"subtitles do not exist: {subtitles}")
    if background_audio is not None and not background_audio.is_file():
        raise FileNotFoundError(f"background_audio does not exist: {background_audio}")
    try:
        start_seconds = float(raw_job.get("start_seconds", 0))
        duration_seconds = float(raw_job["duration_seconds"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid timing in job: {job_id}") from exc
    if start_seconds < 0 or duration_seconds <= 0:
        raise ValueError("start_seconds must be >= 0 and duration_seconds must be > 0")
    output = _resolve_path(str(raw_job.get("output", "")), config_path.parent)
    work_dir = _resolve_path(str(raw_job.get("work_dir", "work")), config_path.parent)
    if not output.name or not work_dir.name:
        raise ValueError("output and work_dir are required")
    job = dict(raw_job)
    job.update({
        "job_id": job_id, "adapter_id": expected, "renderer_module": str(renderer_path),
        "source_video": str(source_video), "subtitles": str(subtitles),
        "start_seconds": start_seconds, "duration_seconds": duration_seconds,
        "output": str(output), "work_dir": str(work_dir),
    })
    if background_audio is not None:
        job["background_audio"] = str(background_audio)
    return job


def ensure_output_available(path: Path, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"output already exists; pass --force to overwrite: {path}")


def render_job(job: dict[str, Any], force: bool = False) -> Path:
    output = Path(job["output"])
    ensure_output_available(output, force)
    renderer = _load_renderer(Path(job["renderer_module"]))
    if callable(getattr(renderer, "render", None)):
        renderer.render(job)
        return output
    work_dir = Path(job["work_dir"])
    clean_video = work_dir / f"{job['job_id']}-clean.mp4"
    ensure_output_available(clean_video, force)
    work_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    scenes = getattr(renderer, job["scene_symbol"])
    renderer.render_clean(scenes, job["start_seconds"], job["duration_seconds"], clean_video)
    renderer.finish(
        clean_video, Path(job["source_video"]), Path(job["subtitles"]),
        job["start_seconds"], job["duration_seconds"], output,
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--job", required=True)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--expected-adapter")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    job = load_job(args.config, args.job, args.expected_adapter, args.registry)
    if args.render:
        output = render_job(job, force=args.force)
        print(json.dumps({"status": "rendered", "output": str(output)}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": "validated", "job": job}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate one course episode package, including every declared asset.

The complete check is intentionally local and read-only. It requires FFmpeg's
``ffprobe`` for media inspection unless ``--skip-media-probe`` is explicitly
passed; that option produces a warning and is not equivalent to full QA.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any


REQUIRED_FILES = (
    "master-16x9.mp4", "douyin-9x16.mp4",
    "cover-bilibili-1146x717.png", "cover-youtube-1280x720.png", "cover-douyin-1080x1920.png",
    "subtitles-zh-Hans.srt", "metadata.json", "qa-report.json", "publish-manifest.json", "publish-state.json",
)
VALID_LOCAL_STATES = {
    "planned", "source_scanned", "script_ready", "audio_ready", "sync_ready", "rendered",
    "local_ready", "metadata_ready", "package_ready", "uploading", "uploaded_draft",
    "remote_verified", "user_reviewed", "scheduled", "published", "url_verified",
}
PUBLIC_STATES = {"scheduled", "published", "url_verified"}
EXPECTED_COVERS = {
    "cover-bilibili-1146x717.png": (1146, 717),
    "cover-youtube-1280x720.png": (1280, 720),
    "cover-douyin-1080x1920.png": (1080, 1920),
}


def _validate_source_provenance(metadata: dict[str, Any]) -> dict[str, Any]:
    path = Path(__file__).with_name("source_provenance.py")
    spec = importlib.util.spec_from_file_location("creator_course_source_provenance", path)
    if spec is None or spec.loader is None:
        return {"ok": False, "errors": [f"source provenance validator unavailable: {path}"], "warnings": [], "checks": []}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_source_provenance(metadata)


def read_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"cannot parse UTF-8 JSON {path.name}: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{path.name} must contain a JSON object")
        return {}
    return data


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _safe_asset_path(package_dir: Path, value: Any) -> tuple[Path | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, "asset path must be a non-empty string"
    raw = Path(value)
    if raw.is_absolute():
        return None, f"asset path must be relative: {value}"
    try:
        resolved = (package_dir / raw).resolve()
        resolved.relative_to(package_dir.resolve())
    except ValueError:
        return None, f"asset path escapes package directory: {value}"
    return resolved, None


def manifest_assets(manifest: dict[str, Any], errors: list[str]) -> list[tuple[str, str, str]]:
    """Return (asset id, relative filename, expected hash) for all known schemas."""
    result: list[tuple[str, str, str]] = []
    files = manifest.get("files")
    hashes = manifest.get("asset_sha256")
    if isinstance(files, dict):
        if not isinstance(hashes, dict):
            errors.append("manifest asset_sha256 must be an object when files is present")
            hashes = {}
        for asset_id, filename in files.items():
            expected = hashes.get(asset_id)
            if not isinstance(expected, str) or len(expected.strip()) != 64:
                errors.append(f"manifest is missing a valid SHA-256 for asset: {asset_id}")
            result.append((str(asset_id), str(filename), str(expected or "")))
        return result

    assets = manifest.get("assets")
    if isinstance(assets, dict):
        for asset_id, payload in assets.items():
            if not isinstance(payload, dict):
                errors.append(f"manifest asset must be an object: {asset_id}")
                continue
            filename = payload.get("filename") or payload.get("path")
            expected = payload.get("sha256")
            if not isinstance(expected, str) or len(expected.strip()) != 64:
                errors.append(f"manifest is missing a valid SHA-256 for asset: {asset_id}")
            result.append((str(asset_id), str(filename or ""), str(expected or "")))
        return result

    legacy = manifest.get("source_sha256")
    if isinstance(legacy, dict):
        for asset_id, filename in (("master", "master-16x9.mp4"), ("vertical", "douyin-9x16.mp4")):
            expected = legacy.get(asset_id)
            if not isinstance(expected, str) or len(expected.strip()) != 64:
                errors.append(f"manifest is missing a valid SHA-256 for asset: {asset_id}")
            result.append((asset_id, filename, str(expected or "")))
        return result

    errors.append("manifest must declare files/asset_sha256, assets, or source_sha256")
    return result


def _probe_video(path: Path, errors: list[str], expected_ratio: float) -> None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        errors.append("ffprobe is required for complete media validation")
        return
    command = [
        ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    if completed.returncode != 0:
        errors.append(f"ffprobe failed for {path.name}: media is not readable")
        return
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        errors.append(f"ffprobe returned invalid JSON for {path.name}")
        return
    streams = payload.get("streams") or []
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if not video:
        errors.append(f"{path.name} is missing a video stream")
    else:
        if video.get("codec_name") != "h264":
            errors.append(f"{path.name} video codec must be h264, got {video.get('codec_name')!r}")
        try:
            width = int(video.get("width"))
            height = int(video.get("height"))
            ratio = width / height
        except (TypeError, ValueError, ZeroDivisionError):
            width = height = 0
            ratio = 0
        if width <= 0 or height <= 0:
            errors.append(f"{path.name} video dimensions are invalid")
        elif abs(ratio - expected_ratio) > 0.03:
            errors.append(f"{path.name} video aspect ratio is unexpected: {width}x{height}")
    if not audio:
        errors.append(f"{path.name} is missing an audio stream")
    elif audio.get("codec_name") != "aac":
        errors.append(f"{path.name} audio codec must be aac, got {audio.get('codec_name')!r}")
    try:
        duration = float((payload.get("format") or {}).get("duration"))
    except (TypeError, ValueError):
        duration = 0
    if duration <= 0:
        errors.append(f"{path.name} must have a positive duration")


def _png_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", header[16:24])


def validate_episode(directory: Path, skip_hash: bool = False, skip_media_probe: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    directory = directory.resolve()
    if not directory.is_dir():
        return {"ok": False, "errors": [f"episode directory not found: {directory}"], "warnings": []}

    for name in REQUIRED_FILES:
        path = directory / name
        if not path.is_file():
            errors.append(f"missing required file: {name}")
        elif path.stat().st_size == 0:
            errors.append(f"empty required file: {name}")

    json_files = ("metadata.json", "qa-report.json", "publish-manifest.json", "publish-state.json")
    parsed = {name: read_json(directory / name, errors) for name in json_files if (directory / name).is_file()}
    metadata = parsed.get("metadata.json", {})
    for platform in ("bilibili", "douyin", "youtube"):
        if platform not in metadata:
            errors.append(f"metadata.json missing platform: {platform}")
    source_result = _validate_source_provenance(metadata)
    errors.extend(f"source provenance: {error}" for error in source_result["errors"])
    warnings.extend(f"source provenance: {warning}" for warning in source_result["warnings"])
    qa = parsed.get("qa-report.json", {})
    if qa.get("status") != "pass":
        errors.append("qa-report.json status must be pass")
    if qa.get("manifest_hashes_match") is False:
        errors.append("qa-report.json reports manifest hash mismatch")
    state = parsed.get("publish-state.json", {})
    if state.get("status") not in VALID_LOCAL_STATES:
        errors.append(f"unknown publish-state status: {state.get('status')!r}")
    manifest = parsed.get("publish-manifest.json", {})
    assets = manifest_assets(manifest, errors)
    for asset_id, filename, expected in assets:
        asset_path, path_error = _safe_asset_path(directory, filename)
        if path_error:
            errors.append(f"{asset_id}: {path_error}")
            continue
        assert asset_path is not None
        if not asset_path.is_file():
            errors.append(f"asset missing: {asset_id} -> {filename}")
            continue
        if not skip_hash and expected and sha256(asset_path) != expected.upper():
            errors.append(f"SHA-256 mismatch for {asset_id}: {filename}")
    if skip_hash:
        warnings.append("hash validation skipped; this is not complete package QA")

    if skip_media_probe:
        warnings.append("media probe skipped; this is not complete technical QA")
    else:
        for filename, expected_ratio in (("master-16x9.mp4", 16 / 9), ("douyin-9x16.mp4", 9 / 16)):
            path = directory / filename
            if path.is_file():
                _probe_video(path, errors, expected_ratio)
    for filename, expected_size in EXPECTED_COVERS.items():
        path = directory / filename
        if path.is_file():
            actual_size = _png_size(path)
            if actual_size != expected_size:
                errors.append(f"{filename} must be {expected_size[0]}x{expected_size[1]}, got {actual_size}")

    if state.get("status") in {"package_ready", "uploaded_draft", "remote_verified"} and not state.get("subtitle_policy"):
        warnings.append("publish-state.json has no explicit subtitle_policy")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode_directory", type=Path)
    parser.add_argument("--skip-hash", action="store_true", help="Skip SHA-256 checks")
    parser.add_argument("--skip-media-probe", action="store_true", help="Skip ffprobe checks, with a warning")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()
    result = validate_episode(args.episode_directory, skip_hash=args.skip_hash, skip_media_probe=args.skip_media_probe)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for warning in result["warnings"]:
            print(f"WARNING: {warning}")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        print("OK" if result["ok"] else "FAILED")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

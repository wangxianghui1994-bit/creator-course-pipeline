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


BASE_REQUIRED_FILES = (
    "master-16x9.mp4", "douyin-9x16.mp4",
    "subtitles-zh-Hans.srt", "metadata.json", "qa-report.json", "publish-manifest.json", "publish-state.json",
)
LEGACY_COVER_FILES = (
    "cover-bilibili-1146x717.png", "cover-youtube-1280x720.png", "cover-douyin-1080x1920.png",
)
VALID_LOCAL_STATES = {
    "planned", "source_scanned", "script_ready", "audio_ready", "sync_ready", "rendered",
    "local_ready", "metadata_ready", "package_ready", "uploading", "uploaded_draft", "draft_saved",
    "remote_verified", "user_reviewed", "scheduled", "published", "url_verified",
}
PUBLIC_STATES = {"scheduled", "published", "url_verified"}
EXPECTED_COVERS = {
    "cover-bilibili-1146x717.png": (1146, 717),
    "cover-youtube-1280x720.png": (1280, 720),
    "cover-douyin-1080x1920.png": (1080, 1920),
}
V12_COVER_PROFILES = {
    "bilibili-landscape": (1146, 717),
    "youtube-landscape": (1280, 720),
    "douyin-landscape": (1440, 1080),
    "douyin-portrait": (1080, 1440),
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


def validate_production_acceptance(
    metadata: dict[str, Any], manifest: dict[str, Any], qa: dict[str, Any]
) -> dict[str, Any]:
    """Validate the opt-in schema 1.2 production acceptance contract.

    Schema 1.1 packages remain readable for backward compatibility. New
    packages must make the audio, subtitle, and platform-cover decisions
    explicit so an omitted background track or unsafe cover cannot look like
    a successful local render.
    """
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[str] = []
    schema = str(metadata.get("package_schema_version", "1.1"))
    if schema == "1.1":
        warnings.append("legacy package schema 1.1: production acceptance fields are not enforced")
        return {"ok": True, "errors": errors, "warnings": warnings, "checks": checks}
    if schema != "1.2":
        errors.append(f"unsupported package_schema_version: {schema!r}")
        return {"ok": False, "errors": errors, "warnings": warnings, "checks": checks}

    audio = metadata.get("audio_design")
    if not isinstance(audio, dict):
        errors.append("audio_design must be declared for package schema 1.2")
    else:
        mode = audio.get("background_mode")
        if mode not in {"light_music", "ambience", "intentional_none"}:
            errors.append("audio_design.background_mode must be light_music, ambience, or intentional_none")
        if mode in {"light_music", "ambience"}:
            asset_id = audio.get("background_asset_id")
            if not isinstance(asset_id, str) or not asset_id.strip():
                errors.append("audio_design.background_asset_id is required when background sound is used")
            else:
                entries = {asset: (filename, expected) for asset, filename, expected in manifest_assets(manifest, [])}
                if asset_id not in entries:
                    errors.append(f"audio background asset is not listed in manifest: {asset_id}")
            if audio.get("rights_status") not in {"cleared", "original", "public_domain", "licensed"}:
                errors.append("audio_design.rights_status must confirm a cleared/original/public_domain/licensed source")
        elif mode == "intentional_none" and not str(audio.get("reason") or "").strip():
            errors.append("audio_design.reason is required when background sound is intentionally omitted")
        if audio.get("mix_reviewed") is not True:
            errors.append("audio_design.mix_reviewed must be true")
        if audio.get("speech_intelligibility_reviewed") is not True:
            errors.append("audio_design.speech_intelligibility_reviewed must be true")
        if not errors:
            checks.append(f"audio design checked: {mode}")

    subtitle = qa.get("subtitle_acceptance")
    if not isinstance(subtitle, dict):
        errors.append("qa-report.json must declare subtitle_acceptance for package schema 1.2")
    else:
        if subtitle.get("timing_source") not in {"word_alignment", "manual_verified"}:
            errors.append("subtitle_acceptance.timing_source must be word_alignment or manual_verified")
        for field in (
            "semantic_segmentation", "proper_nouns_reviewed", "landscape_safe_area_reviewed",
            "vertical_safe_area_reviewed", "full_listen_reviewed",
        ):
            if subtitle.get(field) is not True:
                errors.append(f"subtitle_acceptance.{field} must be true")
        if not any("subtitle_acceptance" in error for error in errors):
            checks.append("subtitle acceptance checked")

    profiles = metadata.get("cover_profiles")
    if not isinstance(profiles, list):
        errors.append("cover_profiles must be a list for package schema 1.2")
    else:
        by_id = {item.get("id"): item for item in profiles if isinstance(item, dict)}
        for profile_id, expected_size in V12_COVER_PROFILES.items():
            profile = by_id.get(profile_id)
            if not isinstance(profile, dict):
                errors.append(f"cover_profiles missing required profile: {profile_id}")
                continue
            if (profile.get("width"), profile.get("height")) != expected_size:
                errors.append(f"cover profile {profile_id} must be {expected_size[0]}x{expected_size[1]}")
            filename = profile.get("filename")
            if not isinstance(filename, str) or not filename.strip():
                errors.append(f"cover profile {profile_id} must declare filename")
            if profile.get("source") != "dedicated_layout":
                errors.append(f"cover profile {profile_id} must use a dedicated_layout, not a screenshot")
        if len(by_id) != len(profiles):
            errors.append("cover_profiles entries must have unique ids")
        if not any("cover profile" in error or "cover_profiles" in error for error in errors):
            checks.append(f"cover profiles checked: {len(profiles)}")

    return {"ok": not errors, "errors": errors, "warnings": warnings, "checks": checks}


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

    metadata_path = directory / "metadata.json"
    metadata_preview = read_json(metadata_path, errors) if metadata_path.is_file() else {}
    schema = str(metadata_preview.get("package_schema_version", "1.1"))
    required_files = list(BASE_REQUIRED_FILES)
    if schema == "1.2":
        profiles = metadata_preview.get("cover_profiles")
        if isinstance(profiles, list):
            required_files.extend(
                str(profile.get("filename"))
                for profile in profiles
                if isinstance(profile, dict) and isinstance(profile.get("filename"), str)
            )
    else:
        required_files.extend(LEGACY_COVER_FILES)
    for name in required_files:
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
    production_result = validate_production_acceptance(metadata, manifest, qa)
    errors.extend(f"production acceptance: {error}" for error in production_result["errors"])
    warnings.extend(f"production acceptance: {warning}" for warning in production_result["warnings"])
    assets = manifest_assets(manifest, errors)
    declared_filenames = {filename for _, filename, _ in assets}
    # QA and state ledgers are control records created after the manifest and
    # are deliberately excluded; every media, subtitle, cover, and metadata
    # asset must still be declared and hashed.
    manifest_required_files = [name for name in required_files if name not in {"qa-report.json", "publish-manifest.json", "publish-state.json"}]
    for required_name in manifest_required_files:
        if (directory / required_name).is_file() and required_name not in declared_filenames:
            errors.append(f"manifest must declare required asset: {required_name}")
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
    if schema == "1.2":
        for profile in metadata.get("cover_profiles", []) if isinstance(metadata.get("cover_profiles"), list) else []:
            if not isinstance(profile, dict):
                continue
            filename = profile.get("filename")
            expected_size = (profile.get("width"), profile.get("height"))
            path = directory / str(filename)
            if path.is_file() and all(isinstance(value, int) for value in expected_size):
                actual_size = _png_size(path)
                if actual_size != expected_size:
                    errors.append(f"{filename} must be {expected_size[0]}x{expected_size[1]}, got {actual_size}")
    else:
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

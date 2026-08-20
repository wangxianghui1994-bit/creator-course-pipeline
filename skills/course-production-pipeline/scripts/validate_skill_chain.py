#!/usr/bin/env python3
"""Validate the local course-production-to-draft chain without publishing."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"module could not be loaded: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _keyword_validator():
    # In the public bundle both Skills are siblings under ``skills``.
    path = Path(__file__).resolve().parents[2] / "multi-platform-publish" / "scripts" / "validate_publish_metadata.py"
    if not path.is_file():
        raise FileNotFoundError(f"keyword validator unavailable: {path}")
    return _load_module(path, "creator_course_publish_metadata")


def _package_validator():
    return _load_module(Path(__file__).with_name("validate_episode_package.py"), "creator_course_package")


def _default_adapter(registry_path: Path) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    errors: list[str] = []
    checks: list[str] = []
    try:
        registry = _read_json(registry_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"registry unreadable: {exc}"], checks
    defaults = [entry for entry in registry.get("adapters", []) if entry.get("status") == "default"]
    if len(defaults) != 1:
        errors.append(f"expected exactly one default adapter, found {len(defaults)}")
        return None, errors, checks
    adapter = defaults[0]
    if not adapter.get("id"):
        errors.append("default adapter has no id")
    entrypoint = adapter.get("entrypoint")
    if not entrypoint:
        errors.append("default adapter has no entrypoint")
    else:
        candidates = [(registry_path.parent / entrypoint).resolve(), (registry_path.parent.parent / entrypoint).resolve()]
        if not any(path.is_file() for path in candidates):
            errors.append(f"default adapter entrypoint missing: {entrypoint}")
    if adapter.get("id"):
        checks.append(f"default adapter: {adapter['id']}")
    return adapter, errors, checks


def is_safe_draft_state(state: dict[str, Any]) -> bool:
    """Keep public verification and scheduling outside the draft validator."""
    if state.get("status") in {"scheduled", "published", "url_verified"}:
        return False
    platforms = state.get("platforms")
    if not isinstance(platforms, dict):
        return False
    return all(
        isinstance(entry, dict) and entry.get("public_url") in (None, "")
        for entry in platforms.values()
    )


def validate_chain(package_dir: Path, registry_path: Path) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    registry_path = registry_path.resolve()
    errors: list[str] = []
    checks: list[str] = []

    adapter, adapter_errors, adapter_checks = _default_adapter(registry_path)
    errors.extend(adapter_errors)
    checks.extend(adapter_checks)

    required = ("publish-manifest.json", "metadata.json", "qa-report.json", "publish-state.json")
    missing = [name for name in required if not (package_dir / name).is_file()]
    if missing:
        errors.extend(f"missing package file: {name}" for name in missing)
        return {"ok": not errors, "errors": errors, "checks": checks}

    try:
        manifest = _read_json(package_dir / "publish-manifest.json")
        metadata = _read_json(package_dir / "metadata.json")
        qa = _read_json(package_dir / "qa-report.json")
        state = _read_json(package_dir / "publish-state.json")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"package JSON unreadable: {exc}")
        return {"ok": False, "errors": errors, "checks": checks}

    try:
        keyword_result = _keyword_validator().validate_metadata(metadata)
    except (OSError, ValueError) as exc:
        keyword_result = {"ok": False, "errors": [str(exc)], "checks": []}
    if not keyword_result["ok"]:
        errors.extend(f"metadata keyword: {error}" for error in keyword_result["errors"])
    else:
        checks.extend(keyword_result["checks"])

    package_result = _package_validator().validate_episode(package_dir)
    errors.extend(f"package: {error}" for error in package_result["errors"])
    checks.extend(f"package warning: {warning}" for warning in package_result["warnings"])

    if qa.get("status") != "pass":
        errors.append(f"qa status is not pass: {qa.get('status')}")
    else:
        checks.append("qa status: pass")

    for source_name, payload in (("metadata", metadata), ("state", state)):
        policy = payload.get("policy") or {}
        if not isinstance(policy, dict):
            errors.append(f"{source_name}.policy must be an object")
            continue
        for key in ("publish", "schedule", "delete"):
            if policy.get(key) is True:
                errors.append(f"{source_name} policy enables forbidden default action: {key}")

    if not is_safe_draft_state(state):
        errors.append(f"publish state is outside safe draft boundary: {state.get('status')!r}")
    else:
        checks.append(f"publish state: {state.get('status')}")
    if adapter:
        checks.append(f"adapter registry checked: {adapter.get('id')}")
    return {"ok": not errors, "errors": errors, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    args = parser.parse_args()
    result = validate_chain(args.package_dir, args.registry)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate a publish-state ledger without contacting a platform."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


VALID_STATES = {
    "local_ready", "metadata_ready", "package_ready", "uploading", "uploaded_draft",
    "draft_saved", "remote_verified", "user_reviewed", "scheduled", "published",
    "url_verified", "login_required", "platform_changed", "upload_failed",
    "draft_unverified", "duplicate_candidate", "needs_manual_action",
}
SAFE_DRAFT_STATES = {
    "local_ready", "metadata_ready", "package_ready", "uploading", "uploaded_draft",
    "draft_saved", "remote_verified", "user_reviewed", "login_required",
    "platform_changed", "upload_failed", "draft_unverified", "duplicate_candidate",
    "needs_manual_action",
}


def load_state(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, [f"cannot parse UTF-8 JSON: {exc}"]
    if not isinstance(data, dict):
        return {}, ["state root must be a JSON object"]
    return data, []


def validate_state(state: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    overall = state.get("status")
    if overall not in VALID_STATES:
        errors.append(f"unknown overall status: {overall!r}")

    platforms = state.get("platforms")
    if not isinstance(platforms, dict):
        return {"ok": False, "errors": errors + ["platforms must be an object"], "warnings": warnings}

    for name, entry in platforms.items():
        if not isinstance(entry, dict):
            errors.append(f"{name}: platform entry must be an object")
            continue
        status = entry.get("status")
        if status not in VALID_STATES:
            errors.append(f"{name}: unknown status {status!r}")
        public_url = entry.get("public_url")
        if status in SAFE_DRAFT_STATES and public_url not in (None, ""):
            errors.append(f"{name}: non-public state must not have public_url")
        if status in {"uploaded_draft", "remote_verified"} and not entry.get("last_verified_at"):
            errors.append(f"{name}: {status} requires last_verified_at")

    policy = str(state.get("subtitle_policy") or "")
    if overall in {"package_ready", "uploaded_draft", "remote_verified"} and not policy:
        warnings.append("subtitle_policy is not explicit")
    if policy and "不上传" not in policy and "do not upload" not in policy.lower():
        warnings.append("subtitle_policy does not explicitly forbid external subtitle upload")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def is_safe_draft_state(state: dict[str, Any]) -> bool:
    """Return whether a ledger is still inside the unpublished safe boundary."""
    if state.get("status") not in SAFE_DRAFT_STATES:
        return False
    return all(
        isinstance(entry, dict) and entry.get("public_url") in (None, "")
        for entry in (state.get("platforms") or {}).values()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state_file", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    state, parse_errors = load_state(args.state_file.resolve())
    result = validate_state(state) if not parse_errors else {"ok": False, "errors": parse_errors, "warnings": []}
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

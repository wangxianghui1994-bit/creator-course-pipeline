#!/usr/bin/env python3
"""Validate canonical, local-first publishing metadata.

The project metadata owns the keyword vocabulary. Platform suggestions are
never treated as authoritative input.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PLATFORM_FIELDS = {
    "douyin": ("keywords", "hashtags"),
    "bilibili": ("tags",),
    "youtube": ("tags",),
}

DISCLOSURE_MODES = {"user_opt_out_by_default", "user_opt_in", "platform_required"}
PLATFORM_DECLARATIONS = {"do_not_proactively_set", "user_decides", "required"}
MANDATORY_GATES = {"pause_for_user_review", "block_until_resolved"}


def _is_string_list(value: Any, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and item.strip() for item in value)
    )


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _validate_list(
    platform: str,
    field: str,
    values: Any,
    core: list[str],
    allowed: set[str],
    errors: list[str],
) -> None:
    if not _is_string_list(values):
        errors.append(f"{platform}.{field} must be a non-empty string list")
        return
    normalized = [value.strip() for value in values]
    duplicate_values = _duplicates(normalized)
    if duplicate_values:
        errors.append(f"{platform}.{field} has duplicate keywords: {', '.join(duplicate_values)}")
    unlisted = [value for value in normalized if value not in allowed]
    if unlisted:
        errors.append(f"{platform}.{field} contains unlisted keywords: {', '.join(unlisted)}")
    missing = [value for value in core if value not in normalized]
    if missing:
        errors.append(f"{platform}.{field} is missing core keywords: {', '.join(missing)}")
    if normalized[: len(core)] != core:
        errors.append(f"{platform}.{field} core keyword order must be: {' → '.join(core)}")


def _validate_disclosure_policy(metadata: dict[str, Any], errors: list[str], checks: list[str]) -> None:
    policy = metadata.get("disclosure_policy")
    if policy is None:
        return
    if not isinstance(policy, dict):
        errors.append("disclosure_policy must be an object")
        return
    mode = policy.get("mode")
    if mode not in DISCLOSURE_MODES:
        errors.append(
            "disclosure_policy.mode must be one of: "
            + ", ".join(sorted(DISCLOSURE_MODES))
        )
    declaration = policy.get("platform_declaration")
    if declaration not in PLATFORM_DECLARATIONS:
        errors.append(
            "disclosure_policy.platform_declaration must be one of: "
            + ", ".join(sorted(PLATFORM_DECLARATIONS))
        )
    gate = policy.get("mandatory_gate")
    if gate not in MANDATORY_GATES:
        errors.append(
            "disclosure_policy.mandatory_gate must be one of: "
            + ", ".join(sorted(MANDATORY_GATES))
        )
    if not errors:
        checks.append(f"disclosure policy: {mode}")


def validate_metadata(metadata: dict[str, Any], platforms: list[str] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    checks: list[str] = []
    _validate_disclosure_policy(metadata, errors, checks)
    policy = metadata.get("keyword_policy")
    if not isinstance(policy, dict):
        return {"ok": False, "errors": ["keyword_policy is required"], "checks": checks}

    core_value = policy.get("core")
    if not _is_string_list(core_value):
        errors.append("keyword_policy.core must be a non-empty string list")
        core: list[str] = []
    else:
        core = [value.strip() for value in core_value]
        duplicate_values = _duplicates(core)
        if duplicate_values:
            errors.append(f"keyword_policy.core has duplicate keywords: {', '.join(duplicate_values)}")

    episode_value = policy.get("episode", [])
    if not _is_string_list(episode_value, allow_empty=True):
        errors.append("keyword_policy.episode must be a string list")
        episode: list[str] = []
    else:
        episode = [value.strip() for value in episode_value]
        duplicate_values = _duplicates(episode)
        if duplicate_values:
            errors.append(f"keyword_policy.episode has duplicate keywords: {', '.join(duplicate_values)}")
        overlap = [value for value in episode if value in core]
        if overlap:
            errors.append(f"keyword_policy.episode repeats core keywords: {', '.join(overlap)}")

    if policy.get("reject_unlisted") is not True:
        errors.append("keyword_policy.reject_unlisted must be true")

    allowed = set(core).union(episode)
    selected = platforms or [
        name for name, value in metadata.items() if name in PLATFORM_FIELDS and isinstance(value, dict)
    ]
    if not selected:
        errors.append("metadata has no supported platform section")

    for platform in selected:
        payload = metadata.get(platform)
        fields = PLATFORM_FIELDS.get(platform)
        if not isinstance(payload, dict):
            errors.append(f"metadata missing platform: {platform}")
            continue
        if not fields:
            errors.append(f"unsupported keyword platform: {platform}")
            continue
        for field in fields:
            if field not in payload:
                errors.append(f"{platform}.{field} is required")
            else:
                _validate_list(platform, field, payload[field], core, allowed, errors)
        checks.append(f"keywords checked: {platform}")

    if not errors and core:
        checks.append(f"core keywords: {' → '.join(core)}")
    return {"ok": not errors, "errors": errors, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata_file", type=Path)
    parser.add_argument("--platform", action="append", dest="platforms")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        metadata = json.loads(args.metadata_file.resolve().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        result = {"ok": False, "errors": [f"cannot parse UTF-8 JSON: {exc}"], "checks": []}
    else:
        result = validate_metadata(metadata, platforms=args.platforms)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for check in result["checks"]:
            print(f"CHECK: {check}")
        print("OK" if result["ok"] else "FAILED")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

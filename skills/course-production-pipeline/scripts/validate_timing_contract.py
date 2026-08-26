#!/usr/bin/env python3
"""Validate semantic subtitle timing and spoken-anchor scene contracts.

This validator is intentionally provider-neutral.  It checks the shape of a
timing/alignment document and an optional scene document without requiring a
particular speech-to-text engine or renderer.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


PUNCTUATION = re.compile(r"[\s\u3000，。！？；：、‘’“”\"'（）()【】\[\]《》〈〉—…,.!?;:/\\]+")


def _normalise(value: str) -> str:
    """Remove whitespace and punctuation for canonical text comparisons."""

    return PUNCTUATION.sub("", value)


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _validate_cues(document: dict[str, Any], errors: list[str], checks: list[str]) -> None:
    timing_source = document.get("timing_source")
    if not isinstance(timing_source, str) or not timing_source.strip():
        errors.append("timing_source must be a non-empty string")
    elif timing_source.lower() in {"fixed_character_split", "fixed_character", "character_average"}:
        errors.append("fixed-character average timing is preview-only and cannot pass formal QA")

    canonical = document.get("canonical_script")
    if not isinstance(canonical, str) or not canonical.strip():
        errors.append("canonical_script must be a non-empty string")

    cues = document.get("semantic_cues")
    if not isinstance(cues, list) or not cues:
        errors.append("semantic_cues must be a non-empty list")
        return

    max_characters = 16
    subtitle_policy = document.get("subtitle_policy")
    if isinstance(subtitle_policy, dict) and _number(subtitle_policy.get("max_characters")):
        max_characters = int(subtitle_policy["max_characters"])
    if max_characters < 1:
        errors.append("subtitle_policy.max_characters must be positive")

    cue_text = []
    previous_end = -1.0
    for index, cue in enumerate(cues, start=1):
        if not isinstance(cue, dict):
            errors.append(f"semantic_cues[{index}] must be an object")
            continue
        text = cue.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"semantic_cues[{index}].text must be non-empty")
        else:
            cue_text.append(text)
            if len(_normalise(text)) > max_characters:
                errors.append(
                    f"semantic_cues[{index}] exceeds max_characters={max_characters}"
                )
        start = cue.get("start")
        end = cue.get("end")
        if not _number(start) or not _number(end):
            errors.append(f"semantic_cues[{index}] requires numeric start and end")
            continue
        if float(start) < 0 or float(end) <= float(start):
            errors.append(f"semantic_cues[{index}] must satisfy 0 <= start < end")
        if float(start) < previous_end - 1e-6:
            errors.append(f"semantic_cues[{index}] overlaps or is out of order")
        previous_end = max(previous_end, float(end))
        if re.search(r"[。！？；：.!?;:]\s*$", text):
            errors.append(f"semantic_cues[{index}] has terminal punctuation")

    if isinstance(canonical, str) and cue_text:
        if _normalise(canonical) != _normalise("".join(cue_text)):
            errors.append("semantic_cues text does not cover canonical_script exactly")

    if timing_source and "align" in timing_source.lower():
        word_timestamps = document.get("word_timestamps")
        if not isinstance(word_timestamps, list) or not word_timestamps:
            errors.append("word-aligned timing requires a non-empty word_timestamps list")
        else:
            checks.append(f"word timestamps present: {len(word_timestamps)}")
    checks.append(f"semantic cues checked: {len(cues)}")


def _validate_beats(document: dict[str, Any], errors: list[str], checks: list[str]) -> None:
    beats = document.get("beats")
    if beats is None:
        return
    if not isinstance(beats, list) or not beats:
        errors.append("beats must be a non-empty list when declared")
        return
    canonical = _normalise(str(document.get("canonical_script", "")))
    previous_end = -1.0
    for index, beat in enumerate(beats, start=1):
        if not isinstance(beat, dict):
            errors.append(f"beats[{index}] must be an object")
            continue
        beat_id = beat.get("beat_id")
        if not isinstance(beat_id, str) or not beat_id.strip():
            errors.append(f"beats[{index}].beat_id must be non-empty")
        start = beat.get("start")
        end = beat.get("end")
        if not _number(start) or not _number(end) or float(end) <= float(start):
            errors.append(f"beats[{index}] must satisfy numeric start < end")
        elif float(start) < previous_end - 1e-6:
            errors.append(f"beats[{index}] overlaps or is out of order")
        if _number(end):
            previous_end = max(previous_end, float(end))

        anchor = beat.get("spoken_anchor")
        anchor_start = beat.get("anchor_start")
        anchor_end = beat.get("anchor_end")
        if not isinstance(anchor, str) or not anchor.strip():
            errors.append(f"beats[{index}].spoken_anchor must be non-empty")
        elif _normalise(anchor) not in canonical:
            errors.append(f"beats[{index}].spoken_anchor is absent from canonical_script")
        if not _number(anchor_start) or not _number(anchor_end):
            errors.append(f"beats[{index}] requires numeric anchor_start and anchor_end")
        elif float(anchor_end) <= float(anchor_start):
            errors.append(f"beats[{index}] anchor_start must be less than anchor_end")
        elif _number(start) and _number(end) and (
            float(anchor_start) < float(start) - 1e-6
            or float(anchor_end) > float(end) + 1e-6
        ):
            errors.append(f"beats[{index}] spoken anchor falls outside its beat")

    checks.append(f"spoken-anchor beats checked: {len(beats)}")


def validate_timing_contract(
    alignment: dict[str, Any], scenes: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return a stable JSON-compatible validation result."""

    errors: list[str] = []
    checks: list[str] = []
    _validate_cues(alignment, errors, checks)
    if scenes is not None:
        scene_timing_source = scenes.get("timing_source")
        if scene_timing_source != alignment.get("timing_source"):
            errors.append("scene timing_source must match alignment timing_source")
        scene_document = dict(alignment)
        scene_document["beats"] = scenes.get("beats")
        _validate_beats(scene_document, errors, checks)
    return {"ok": not errors, "errors": errors, "warnings": [], "checks": checks}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate semantic subtitle timing and spoken-anchor beats"
    )
    parser.add_argument("--alignment", required=True, type=Path)
    parser.add_argument("--scenes", type=Path)
    args = parser.parse_args(argv)
    try:
        alignment = _load(args.alignment)
        scenes = _load(args.scenes) if args.scenes else None
        result = validate_timing_contract(alignment, scenes)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"ok": False, "errors": [str(exc)], "warnings": [], "checks": []}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

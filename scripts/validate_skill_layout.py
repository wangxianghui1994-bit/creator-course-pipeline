#!/usr/bin/env python3
"""Lightweight local layout check; CI also runs the pinned skills-ref tool."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("course-production-pipeline", "multi-platform-publish")


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"missing YAML frontmatter: {path}")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError(f"unterminated YAML frontmatter: {path}")
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip('"')
    return values


def validate() -> list[str]:
    errors: list[str] = []
    for name in SKILLS:
        directory = ROOT / "skills" / name
        skill_file = directory / "SKILL.md"
        if not skill_file.is_file():
            errors.append(f"missing SKILL.md: {name}")
            continue
        if len(skill_file.read_text(encoding="utf-8").splitlines()) > 500:
            errors.append(f"SKILL.md is over 500 lines: {name}")
        try:
            frontmatter = _frontmatter(skill_file)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if frontmatter.get("name") != name:
            errors.append(f"frontmatter name must match directory: {name}")
        if not re.fullmatch(r"[a-z0-9-]{1,64}", frontmatter.get("name", "")):
            errors.append(f"invalid Skill name: {name}")
        if not frontmatter.get("description"):
            errors.append(f"description is required: {name}")
        if not frontmatter.get("license"):
            errors.append(f"license is required: {name}")
        if not frontmatter.get("compatibility"):
            errors.append(f"compatibility is required: {name}")
        if not (directory / "agents" / "openai.yaml").is_file():
            errors.append(f"missing agents/openai.yaml: {name}")
        if not (directory / "scripts").is_dir():
            errors.append(f"missing scripts directory: {name}")
    return errors


def main() -> int:
    errors = validate()
    for error in errors:
        print(f"ERROR: {error}")
    print("OK" if not errors else "FAILED")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

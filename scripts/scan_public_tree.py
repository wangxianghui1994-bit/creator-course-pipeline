#!/usr/bin/env python3
"""Reject common personal paths and secret-like material from the public tree."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".json", ".py", ".yaml", ".yml", ".toml", ".txt", ".xml"}
FORBIDDEN = (
    re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE),
    re.compile(r"(?:^|[\\/])\.codex(?:$|[\\/])", re.IGNORECASE),
    re.compile(r"(?:cookie|sessionid|access[_-]?token|refresh[_-]?token)\s*[:=]\s*[^\s\"']+", re.IGNORECASE),
)


def scan() -> list[str]:
    errors: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in FORBIDDEN:
            if pattern.search(text):
                errors.append(f"forbidden personal or secret-like content: {path.relative_to(ROOT)}")
                break
    return errors


def main() -> int:
    errors = scan()
    for error in errors:
        print(f"ERROR: {error}")
    print("OK" if not errors else "FAILED")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

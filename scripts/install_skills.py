#!/usr/bin/env python3
"""Preview or safely install the two public Skills into a Codex skills dir."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_NAMES = ("course-production-pipeline", "multi-platform-publish")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)).replace("\\", "/"): _sha256(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def plan_install(target: Path) -> dict[str, object]:
    actions = []
    for name in SKILL_NAMES:
        source = ROOT / "skills" / name
        destination = target / name
        actions.append({
            "skill": name,
            "source": str(source),
            "destination": str(destination),
            "exists": destination.exists(),
            "action": "backup-then-replace" if destination.exists() else "install",
        })
    return {"mode": "preview", "target": str(target), "actions": actions}


def apply_install(target: Path) -> dict[str, object]:
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = target.parent / "creator-course-pipeline-backups" / stamp
    backups = []
    installed = []
    for name in SKILL_NAMES:
        source = ROOT / "skills" / name
        destination = target / name
        if not source.is_dir() or not (source / "SKILL.md").is_file():
            raise FileNotFoundError(f"source Skill is incomplete: {source}")
        if destination.exists():
            backup = backup_root / name
            backup_root.mkdir(parents=True, exist_ok=True)
            shutil.copytree(destination, backup)
            backups.append({"skill": name, "path": str(backup), "sha256": _manifest(backup)})
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
        installed.append({"skill": name, "path": str(destination), "sha256": _manifest(destination)})
    result = {"mode": "applied", "target": str(target), "backups": backups, "installed": installed}
    if backups:
        (backup_root / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=Path.home() / ".codex" / "skills")
    parser.add_argument("--apply", action="store_true", help="write after backing up existing Skills")
    args = parser.parse_args()
    target = args.target.expanduser().resolve()
    result = apply_install(target) if args.apply else plan_install(target)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

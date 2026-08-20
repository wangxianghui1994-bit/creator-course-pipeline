#!/usr/bin/env python3
"""Orchestrate local rendering and safe draft-package validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from run_default_video_adapter import load_job, render_job
from validate_skill_chain import validate_chain


def run_chain(
    config_path: Path,
    job_id: str,
    package_dir: Path,
    registry_path: Path,
    *,
    render: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    job = load_job(config_path, job_id, registry_path=registry_path)
    package = validate_chain(package_dir, registry_path)
    result: dict[str, Any] = {
        "ok": package["ok"],
        "status": "validated" if package["ok"] else "blocked",
        "adapter_job": job,
        "package": package,
    }
    if not package["ok"]:
        return result
    if render:
        output = render_job(job, force=force)
        result["status"] = "rendered"
        result["output"] = str(output)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--job", required=True)
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run_chain(
        args.config, args.job, args.package_dir, args.registry,
        render=args.render, force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

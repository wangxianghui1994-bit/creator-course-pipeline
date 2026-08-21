#!/usr/bin/env python3
"""Validate optional, provider-neutral source provenance metadata."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


SOURCE_TYPES = {"notebooklm", "local_file", "url", "user_input", "other"}
SNAPSHOT_STATUSES = {"captured", "not_captured", "not_applicable"}
SECRET_MARKERS = re.compile(
    r"(?:access[_-]?token|api[_-]?key|authorization|bearer|cookie|password|secret|sessionid|refresh[_-]?token)\s*[=:]",
    re.IGNORECASE,
)
DRIVE_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


def validate_source_provenance(metadata: dict[str, Any]) -> dict[str, Any]:
    """Validate the optional ``metadata.source_provenance`` contract.

    The public package stores only a sanitized reference. Private URLs,
    credentials, cookies, and provider-specific local paths belong in a
    private trace ledger, not in a course package or public repository.
    """

    errors: list[str] = []
    warnings: list[str] = []
    checks: list[str] = []
    value = metadata.get("source_provenance")
    if value is None:
        checks.append("source provenance: not declared (optional)")
        return {"ok": True, "errors": errors, "warnings": warnings, "checks": checks}
    if not isinstance(value, dict):
        return {
            "ok": False,
            "errors": ["source_provenance must be an object when present"],
            "warnings": warnings,
            "checks": checks,
        }

    source_type = value.get("source_type")
    source_ref = value.get("source_ref")
    snapshot_status = value.get("snapshot_status")
    citation_count = value.get("citation_count")
    user_reviewed = value.get("user_reviewed")

    if source_type not in SOURCE_TYPES:
        errors.append(f"source_provenance.source_type must be one of: {', '.join(sorted(SOURCE_TYPES))}")
    if not isinstance(source_ref, str) or not source_ref.strip():
        errors.append("source_provenance.source_ref must be a non-empty sanitized reference")
    else:
        reference = source_ref.strip()
        if "://" in reference or Path(reference).is_absolute() or DRIVE_ABSOLUTE_PATH.match(reference):
            errors.append("source_provenance.source_ref must not contain a private URL or absolute path")
        if "\\" in reference or any(part == ".." for part in Path(reference).parts):
            errors.append("source_provenance.source_ref must not contain a traversal path")
        if SECRET_MARKERS.search(reference):
            errors.append("source_provenance.source_ref must not contain secret-like material")
    if snapshot_status not in SNAPSHOT_STATUSES:
        errors.append(
            "source_provenance.snapshot_status must be one of: "
            + ", ".join(sorted(SNAPSHOT_STATUSES))
        )
    if isinstance(citation_count, bool) or not isinstance(citation_count, int) or citation_count < 0:
        errors.append("source_provenance.citation_count must be a non-negative integer")
    if not isinstance(user_reviewed, bool):
        errors.append("source_provenance.user_reviewed must be boolean")

    if source_type == "notebooklm":
        if snapshot_status != "captured":
            errors.append("NotebookLM source requires a captured source snapshot")
        if citation_count == 0:
            errors.append("NotebookLM source requires at least one recorded citation")
        if user_reviewed is not True:
            errors.append("NotebookLM source requires human review before course use")
        checks.append("source provenance: NotebookLM reference checked")
    elif source_type:
        checks.append(f"source provenance: {source_type} reference checked")

    return {"ok": not errors, "errors": errors, "warnings": warnings, "checks": checks}

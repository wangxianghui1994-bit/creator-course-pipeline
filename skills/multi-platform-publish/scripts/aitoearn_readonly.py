#!/usr/bin/env python3
"""Allow-list-only GET access to AiToEarn's public read endpoints.

This module deliberately does not implement upload signing, asset confirmation,
Flow creation, immediate publication, scheduling, deletion, or comments.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable


DEFAULT_BASE_URL = "https://aitoearn.cn"
_SAFE_PART = re.compile(r"^[A-Za-z0-9_.-]+$")


def _part(value: str, label: str) -> str:
    if not isinstance(value, str) or not _SAFE_PART.fullmatch(value):
        raise ValueError(f"invalid {label}")
    return value


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(word in lowered for word in ("key", "token", "secret", "cookie", "password", "authorization")):
                clean[str(key)] = "[REDACTED]"
            else:
                clean[str(key)] = _redact(item)
        return clean
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


class AiToEarnReadOnlyClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        transport: Callable[[str, str, dict[str, str]], dict[str, Any]] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._transport = transport

    def _api_key(self) -> str:
        value = os.environ.get("AITOEARN_API_KEY", "")
        if not value:
            raise RuntimeError("AITOEARN_API_KEY is not set in the current process")
        return value

    def _allowed(self, path: str) -> bool:
        patterns = (
            r"^/api/v2/channels/platforms$",
            r"^/api/v2/channels/accounts$",
            r"^/api/v2/channels/platforms/[A-Za-z0-9_.-]+/publish-options$",
            r"^/api/v2/channels/publish/flows/[A-Za-z0-9_.-]+$",
            r"^/api/v2/channels/publish/records/[A-Za-z0-9_.-]+$",
            r"^/api/v2/channels/works/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
        )
        return any(re.fullmatch(pattern, path) for pattern in patterns)

    def request(self, method: str, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        if method.upper() != "GET":
            raise ValueError("AiToEarn read-only client permits GET only")
        if not self._allowed(path):
            raise ValueError("AiToEarn path is not in the read-only allow-list")
        key = self._api_key()
        query = urllib.parse.urlencode(params or {})
        final_path = f"{path}?{query}" if query else path
        if self._transport:
            return _redact(self._transport("GET", final_path, {"X-Api-Key": key}))
        request = urllib.request.Request(
            f"{self.base_url}{final_path}",
            method="GET",
            headers={"Accept": "application/json", "X-Api-Key": key, "User-Agent": "creator-course-pipeline/0.1"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"AiToEarn GET failed with HTTP {exc.code}") from None
        except urllib.error.URLError as exc:
            raise RuntimeError(f"AiToEarn GET failed: {exc.reason}") from None
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RuntimeError("AiToEarn returned non-JSON data") from None
        if not isinstance(payload, dict):
            raise RuntimeError("AiToEarn response root is not an object")
        return _redact(payload)

    def call(self, operation: str, **kwargs: str) -> dict[str, Any]:
        if operation == "platforms":
            return self.request("GET", "/api/v2/channels/platforms")
        if operation == "accounts":
            return self.request("GET", "/api/v2/channels/accounts")
        if operation == "options":
            return self.request("GET", f"/api/v2/channels/platforms/{_part(kwargs['platform'], 'platform')}/publish-options")
        if operation == "flow":
            return self.request("GET", f"/api/v2/channels/publish/flows/{_part(kwargs['flow_id'], 'flow id')}")
        if operation == "record":
            return self.request("GET", f"/api/v2/channels/publish/records/{_part(kwargs['record_id'], 'record id')}")
        if operation == "work":
            return self.request("GET", f"/api/v2/channels/works/{_part(kwargs['platform'], 'platform')}/{_part(kwargs['work_id'], 'work id')}")
        raise ValueError(f"unsupported read-only operation: {operation}")


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"code": payload.get("code"), "message": payload.get("message")}
    for key in ("data", "result"):
        value = payload.get(key)
        if isinstance(value, list):
            summary[f"{key}_count"] = len(value)
        elif isinstance(value, dict):
            summary[f"{key}_keys"] = sorted(str(item) for item in value.keys())[:30]
    return {key: value for key, value in summary.items() if value is not None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("platforms", "accounts", "options", "flow", "record", "work"))
    parser.add_argument("--platform")
    parser.add_argument("--flow-id")
    parser.add_argument("--record-id")
    parser.add_argument("--work-id")
    parser.add_argument("--json", action="store_true", help="print redacted response rather than a summary")
    args = parser.parse_args()
    kwargs = {key: value for key, value in {
        "platform": args.platform, "flow_id": args.flow_id,
        "record_id": args.record_id, "work_id": args.work_id,
    }.items() if value is not None}
    try:
        payload = AiToEarnReadOnlyClient().call(args.operation, **kwargs)
    except (RuntimeError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(payload if args.json else _summary(payload), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

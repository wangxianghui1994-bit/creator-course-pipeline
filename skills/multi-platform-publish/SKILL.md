---
name: multi-platform-publish
description: Prepare and inspect metadata, keyword policy, unpublished draft state, and read-only AiToEarn capability queries for Bilibili, Douyin, YouTube, and related workflows. Use it when a course package needs canonical keywords, platform payloads, state validation, or a safe handoff. It does not upload, publish, schedule, delete, comment, or automate browser pages.
license: MIT
compatibility: Requires Python 3.11+. AiToEarn read-only queries additionally require AITOEARN_API_KEY in the current process environment and network access.
metadata:
  version: "0.1.0"
  repository: "wangxianghui1994-bit/creator-course-pipeline"
---

# Multi-platform draft preparation

The local metadata is authoritative. Platform-generated suggestions are input
to review, never an automatic replacement for the project keyword policy.

## Keyword policy

Define a non-empty ordered list in `metadata.json`:

```json
"keyword_policy": {
  "core": ["topic", "method"],
  "episode": ["episode-specific"],
  "reject_unlisted": true
}
```

The first `core` items must appear in that order in every selected platform
keyword field. `episode` items are optional extensions and may not repeat the
core list. Duplicates and unlisted platform recommendations fail validation.
For Douyin, `keywords` and `hashtags` are separate fields and are both checked.

```powershell
python skills/multi-platform-publish/scripts/validate_publish_metadata.py metadata.json
python skills/multi-platform-publish/scripts/validate_publish_state.py publish-state.json
```

## Safe state boundary

The local ledger may record preparation and an unpublished draft. The course
chain rejects `scheduled`, `published`, and `url_verified`, and it requires
null public URLs before publication. Human review and platform confirmation
remain explicit steps.

## AiToEarn read-only client

The optional `aitoearn_readonly.py` client reads `AITOEARN_API_KEY` only from
the current process environment. It uses a fixed allow-list of GET operations:
platform metadata, account summaries, dynamic publish options, Flow details,
publish-record details, and work details. It redacts response fields that look
like keys, tokens, cookies, secrets, passwords, or authorization data.

It intentionally does not implement signed upload, asset confirmation, Flow
creation, immediate or scheduled publication, deletion, comments, or arbitrary
URL requests. A successful platform discovery response is evidence of read
access only, not evidence that upload or publication is available.

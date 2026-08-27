---
name: multi-platform-publish
description: Use when a course package needs canonical keywords, platform payloads, unpublished-draft state validation, or a guarded Bilibili/Douyin/YouTube browser handoff.
license: MIT
metadata:
  version: "0.2.0"
  repository: "wangxianghui1994-bit/creator-course-pipeline"
  compatibility: "Requires Python 3.11+. AiToEarn read-only queries additionally require AITOEARN_API_KEY in the current process environment and network access."
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

## AI declaration policy

Keep platform AI declarations separate from the internal production record.
Projects that do not want a declaration added by default can set:

```json
"disclosure_policy": {
  "mode": "user_opt_out_by_default",
  "platform_declaration": "do_not_proactively_set",
  "mandatory_gate": "pause_for_user_review"
}
```

For that mode, do not fill, tick, or copy an AI-generation declaration into a
platform payload unless the user explicitly changes the decision. If the
platform makes the field mandatory, pause with `needs_manual_action`; never
silently bypass the gate. A user's manual change takes precedence, but it is
not remote verification until the visible draft field is read back.

```powershell
python skills/multi-platform-publish/scripts/validate_publish_metadata.py metadata.json
python skills/multi-platform-publish/scripts/validate_publish_state.py publish-state.json
```

## Safe state boundary

The local ledger may record preparation and an unpublished draft. The course
chain rejects `scheduled`, `published`, and `url_verified`, and it requires
null public URLs before publication. Human review and platform confirmation
remain explicit steps.

## Guarded browser handoff

Browser work is a controlled handoff, not an autopilot. Claim one existing tab,
batch DOM reads and fills, wait on visible state changes, and distinguish
`uploading`, `uploaded_draft`, `draft_saved`, and `remote_verified`. Two
authorization failures trigger one manual file selection rather than another
authorization loop. Duplicate candidates, mandatory declarations, public or
destructive actions, ambiguous fields, and any user stop/change request pause
the handoff. See `references/browser-draft-handoff.md`.

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

# Creator Course Pipeline

Reusable Agent Skills for producing inspectable course-video packages and
preparing unpublished multi-platform drafts.

This release is a safe workflow kit. It keeps local course metadata and
technical checks authoritative, while leaving any public submission to a
human-controlled step.

## What is included

- `course-production-pipeline`: numbered episode workflow, adapter registry,
  local FFmpeg rendering, subtitle burn-in, manifests, media QA, optional
  source provenance, and draft chain validation.
- `multi-platform-publish`: canonical keyword validation, draft-state checks,
  and a fixed allow-list AiToEarn read-only client.
- A synthetic demo that generates its own video, audio, subtitles, and covers.
- A preview-first installer that backs up an existing Skill before applying a
  replacement.
- A configurable platform-disclosure policy; it does not silently select an AI
  declaration and pauses if a platform makes one mandatory.

## Boundaries

Implemented: local package generation, all-asset SHA-256 checks, path-traversal
protection, FFprobe media checks, cover dimension checks, adapter interfaces,
optional source provenance checks, canonical keywords, safe state-machine
checks, and read-only AiToEarn capability queries.

Not implemented: automatic public publishing, scheduled publishing, deletion,
comments, arbitrary URL requests, upload signing, asset confirmation, Flow
creation, or browser-page automation. A successful AiToEarn read query proves
only that the selected read endpoint responded; it does not prove upload or
publication permission.

## Quick start

```powershell
python scripts/create_demo_assets.py --output examples/demo/generated
python skills/course-production-pipeline/scripts/validate_episode_package.py examples/demo/generated/EP00-demo
python skills/course-production-pipeline/scripts/validate_skill_chain.py --package-dir examples/demo/generated/EP00-demo --registry examples/demo/generated/registry.json
```

Install into Codex with a preview first:

```powershell
python scripts/install_skills.py
python scripts/install_skills.py --apply
```

Use `--target` to preview or install into another skills directory. `--apply`
backs up existing matching Skill directories to a sibling backup directory and
prints SHA-256 manifests.

## Source provenance

Source provenance is optional. A package can use local files or user-provided
material without NotebookLM. If `metadata.json` declares `source_type` as
`notebooklm`, the validator requires a captured snapshot, at least one
recorded citation, and human review. The Skill does not connect to NotebookLM
or copy private research into the package; it checks a sanitized reference.
See `skills/course-production-pipeline/references/source-material-policy.md`.

## Keyword metadata

The project owns the ordered core list; it is not hard-coded in the validator.
See `examples/demo/metadata.json` for a generic course and
`examples/yangming-course/metadata.json` for a metadata-only example using:

`阳明心学 → 致良知 → 心即理 → 企业AI转型 → 企业家`

Platform suggestions outside `core + episode` fail validation. Douyin
`keywords` and `hashtags` are kept as separate fields.

Platform AI declarations are controlled separately through
`disclosure_policy`. The current example uses `user_opt_out_by_default`, which
leaves that field unset unless the user changes it; a mandatory platform gate
still requires manual review.

## AiToEarn read-only query

Set `AITOEARN_API_KEY` in the current process environment; do not place it in a
file or command argument:

```powershell
$env:AITOEARN_API_KEY = '...'
python skills/multi-platform-publish/scripts/aitoearn_readonly.py platforms
```

The client reads only fixed GET endpoints and redacts sensitive-looking
response fields. It never prints the key.

## Installable Skill layout

The two directories under `skills/` follow the [Agent Skills
specification](https://agentskills.io/specification). The repository pins the
official `skills-ref` validation commit in CI. The project is MIT licensed; see
`LICENSE`.

## Contributing and security

Read `CONTRIBUTING.md` before opening a pull request. Never submit API keys,
cookies, account identifiers, private absolute paths, real course media,
cloned voices, platform screenshots, or draft evidence. Report a security
issue privately according to `SECURITY.md`.

---
name: course-production-pipeline
description: Use when a numbered course episode needs reproducible rendering, narration and background-sound mixing, word-aligned subtitles, native horizontal/vertical layouts, platform-safe covers, package QA, or a guarded draft handoff.
license: MIT
metadata:
  version: "0.3.0"
  repository: "wangxianghui1994-bit/creator-course-pipeline"
  compatibility: "Requires Python 3.11+, FFmpeg/ffprobe for complete media QA, and a local adapter registry. Works on Windows and Ubuntu."
---

# Course production pipeline

Use this Skill to turn a numbered episode into an inspectable local package. It
is a production and handoff workflow, not a platform autopilot.

## Safe workflow

1. Keep source media, scripts, audio, subtitles, and the episode metadata in a
   project directory.
2. Choose exactly one adapter whose registry entry has `status: default`.
3. Render locally with `run_default_video_adapter.py`. The new adapter contract
   is `render(job)`; the older `render_clean + finish + scene_symbol` contract
   remains supported for private adapters.
4. Build a package containing the two videos, declared platform cover profiles,
   SRT, metadata, QA, manifest, and publish-state ledger. New packages use
   package schema `1.2`; schema `1.1` remains readable as legacy.
5. Run `validate_episode_package.py` with FFmpeg available. A media-probe skip
   is an explicit degraded check, not a passing full QA result.
6. Run `validate_skill_chain.py` before any handoff to the publishing Skill.

## AI disclosure handling

Platform AI declarations are a project-level choice, separate from private
production provenance. A project may declare this policy in `metadata.json`:

```json
"disclosure_policy": {
  "mode": "user_opt_out_by_default",
  "platform_declaration": "do_not_proactively_set",
  "mandatory_gate": "pause_for_user_review"
}
```

With `user_opt_out_by_default`, newly generated titles, descriptions, covers,
and platform payloads must not proactively add or select an AI-generation
declaration. Do not change existing packages retroactively. If a platform
requires a declaration before it will accept the submission, stop at the
human-review gate and ask the user; this workflow setting is not a legal or
platform-policy determination.

## Audio, subtitles, and covers

New schema `1.2` packages must declare `audio_design` and a `subtitle_acceptance`
record in QA. The default background mode is `light_music`; `ambience` and an
explicitly justified `intentional_none` are also valid. A used background asset
must be listed in the manifest with a SHA-256 and cleared/original/public-domain
or licensed rights. Human mix and speech-intelligibility review are required.
The public FFmpeg adapter accepts `background_audio` and a low `background_gain`
for a voice-first mix; private adapters must provide an equivalent receipt.

Formal subtitles must come from word-aligned timing or a manually verified
timing document. Fixed-character average splitting is preview-only. Review
semantic phrases, proper nouns, overlap, and both landscape and portrait safe
areas after subtitles are burned in. Keep subtitles as the final video layer.

Declare platform-native `cover_profiles` rather than inferring a cover from a
video frame. The validator checks the declared PNG dimensions; a dedicated
layout is required for new packages. Recheck platform requirements when they
change instead of hard-coding a stale crop.

See `references/production-acceptance.md` for the failure-recovery checklist.

## Timing and visual synchronization

Formal subtitles must come from word-aligned timing or a manually verified
timing document. Fixed-character average splitting is suitable only for a
temporary preview and cannot pass formal acceptance. Keep subtitle text as
natural semantic phrases: one line, no terminal punctuation, and no split
names, numbers, or fixed phrases.

When scenes are driven by narration, each visual beat should declare a unique
`beat_id`, `start`, `end`, `spoken_anchor`, `anchor_start`, and `anchor_end`.
The spoken anchor must occur inside its beat, beats must be ordered without
overlap, and the key reveal should land close to the anchor. Prefer a short
cue-level fade rather than a per-character typewriter effect. Render subtitles
last so they stay above the whiteboard content and can be checked separately
for horizontal and vertical safe areas.

Validate the public timing contract with:

```powershell
python skills/course-production-pipeline/scripts/validate_timing_contract.py `
  --alignment path/to/alignment.json --scenes path/to/scenes.json
```

## Optional source provenance

`metadata.json` may declare a provider-neutral `source_provenance` object. It
is optional: packages that use local files, user-provided material, or no
formal source record can omit it. When the source is NotebookLM, the package
validator requires a captured source snapshot, at least one recorded citation,
and human review before course use.

This is a provenance contract, not a NotebookLM connector. The public Skill
does not log in, query notebooks, read private URLs, or copy raw NotebookLM
answers into a package. Keep the actual snapshot and trace ledger private and
put only a sanitized opaque reference in public metadata. See
`references/source-material-policy.md` for the schema and boundaries.

## Commands

```powershell
python skills/course-production-pipeline/scripts/run_default_video_adapter.py `
  --config examples/demo/generated/jobs.json --job master `
  --registry examples/demo/generated/registry.json --render

python skills/course-production-pipeline/scripts/validate_episode_package.py `
  examples/demo/generated/EP00-demo

python skills/course-production-pipeline/scripts/validate_skill_chain.py `
  --package-dir examples/demo/generated/EP00-demo `
  --registry examples/demo/generated/registry.json
```

The bundled `scripts/create_demo_assets.py` makes a synthetic source video,
subtitles, covers, and a complete package, so the commands can be tried
without a course file or a platform account.

## Adapter registry

`references/tool-registry.json` is a public template. For a private project,
create a project-local registry and point the commands at it. Do not publish
account identifiers, private absolute paths, draft evidence, or proprietary
renderer modules in the public registry.

## Package boundary

The package validator checks every manifest asset, rejects absolute and
traversal paths, verifies SHA-256 values, probes H.264/AAC video streams and
duration, and checks the actual PNG cover dimensions. The chain validator also
blocks `scheduled`, `published`, and `url_verified` states and any non-null
public URL. It also validates declared source provenance and rejects
credential-bearing or private source references. A package can be locally
ready or an unpublished draft, but the user must decide any platform
submission or public release.

The public repository contains only provider-neutral contracts and synthetic
examples. Keep course scripts, voice files, private adapter registries,
NotebookLM links, account state, and local absolute paths in a private project
registry.

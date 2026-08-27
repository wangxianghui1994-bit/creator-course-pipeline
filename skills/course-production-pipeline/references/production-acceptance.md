# Production acceptance and recovery

Use this checklist before a full render and again before handing a package to a
publishing workflow. It records decisions and evidence; it does not replace a
human watch-through.

## Gate order

1. **Source** — Confirm the real file exists with `Test-Path`, non-zero size,
   SHA-256, and `ffprobe`. A browser download record is not an asset.
2. **Script and voice** — Separate source facts from modern interpretation;
   rewrite the approved script in the creator's expression before cloning a
   voice. Check proper-noun pronunciation, cadence, and loudness.
3. **Sample** — Render a representative short sample. Approve narration,
   pacing, visual language, subtitles, and audio design before the full run.
4. **Timeline** — Generate word alignment, semantic subtitle cues, and visual
   beats from one canonical timeline. Every beat has a unique `beat_id` and an
   in-range `spoken_anchor`.
5. **Audio design** — Choose `light_music`, `ambience`, or
   `intentional_none` explicitly. For a background track, record its manifest
   asset ID, rights status, mix review, and speech-intelligibility review.
6. **Render** — Keep native landscape and portrait layouts. Render subtitles
   last. On Windows, if direct MP4 export reports an `ffmpeg ENOENT`, export a
   PNG sequence and compose it with an explicit FFmpeg executable.
7. **Covers** — Generate dedicated platform layouts using current dimensions
   and safe areas. Do not use a video screenshot as a cover. Inspect text at
   the platform's crop preview.
8. **Package** — Use an immutable, non-empty output directory. List every
   package asset in the manifest, then run the full validator last. Any later
   state, metadata, or readback edit requires a fresh manifest and QA run.

## Common failures

| Symptom | Correct response |
| --- | --- |
| Download history has a video but no file | Stop; locate the real file and probe it. |
| NotebookLM/MCP authentication loops | Verify health once; after a failed recovery, use the ordinary-page/manual-download path. |
| Direct HyperFrames MP4 fails on Windows | Keep the source render; use PNG sequence plus explicit FFmpeg. |
| Fixed-character subtitles look acceptable | Reject for formal use; align words and regroup semantic phrases. |
| One orientation is ready | Do not crop it into the other; render and inspect a native layout. |
| BGM is mentioned but no asset or mix receipt exists | Treat background sound as missing; add it or record intentional silence. |
| A platform flags the cover | Regenerate the platform-native profile; do not keep a screenshot crop. |
| State was edited after QA | Rebuild the manifest and rerun QA; old output is historical only. |

## Release boundary

`local_ready` and `package_ready` prove only local evidence. A draft is not
saved until the platform confirms it, and a draft is not remotely verified
until it is reopened and the visible fields are read back. Never infer either
state from a local package, an upload progress bar, or a browser history entry.

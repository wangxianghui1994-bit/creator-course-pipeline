# Capability table

This table describes the boundary of the public release. It is deliberately
not a record of any user's accounts or drafts.

| Area | v0.2.0 behavior | Evidence boundary |
| --- | --- | --- |
| Local course package | Implemented | Synthetic FFmpeg/FFprobe end-to-end test |
| Optional source provenance | Implemented | Sanitized metadata contract and NotebookLM safety tests; no remote connector |
| Canonical keywords | Implemented | Generic core/episode validator tests and metadata-only examples |
| Draft state machine | Implemented | Public states are blocked by the chain validator |
| AiToEarn platform discovery | Read-only GET implemented | A maintainer smoke test returned `code=0` and a platform list; this proves read discovery only |
| AiToEarn account/options/Flow/record/work queries | Read-only GET allow-list implemented | Endpoint responses are summarized and redacted; no write operation is exposed |
| Upload or publication | Not provided | No upload signing, confirmation, Flow creation, submit, schedule, delete, comment, or browser automation |

The AiToEarn client uses the documented `X-Api-Key` header and reads the key
only from `AITOEARN_API_KEY` in the current process. The repository contains no
key, cookie, account identifier, draft identifier, or platform screenshot.

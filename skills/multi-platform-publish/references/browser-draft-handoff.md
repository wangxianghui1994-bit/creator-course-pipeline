# Guarded browser draft handoff

This is a human-controlled handoff checklist, not browser automation. One task
owns one existing tab and one target platform at a time. Use the exact browser,
URL, title, and tab ID already in scope; do not open a second upload page just
because discovery was slow.

## State contract

Record only the strongest state supported by visible evidence:

| State | Evidence required |
| --- | --- |
| `uploading` | The platform is still transferring the selected file. |
| `uploaded_draft` | The upload is complete, but save has not been confirmed. |
| `draft_saved` | The platform confirms the form was saved as an unpublished draft. |
| `remote_verified` | Draft management was reopened and the video, title, cover, tags, declaration, and visibility were read back. |

An upload bar, local file, browser history entry, or stale local ledger cannot
prove `draft_saved` or `remote_verified`.

## Fast path

1. Claim the exact existing tab once and confirm its URL and page title.
2. Inspect the semantic/DOM tree once, then batch independent reads and fills.
3. Use condition-based waits for upload completion, preview readiness, and save
   confirmation. Do not chain fixed sleeps or repeated full screenshots.
4. Prefer visible labels and DOM controls. If a hidden file input does not
   open a chooser, use the page's visible upload button.
5. After two authorization failures, stop requesting authorization. Ask the user
   for one manual file selection of the exact video, then continue from the same tab.
6. Reopen the draft from the management page before calling it verified.

## Stop conditions

Stop and report `needs_manual_action` when any of these appears:

- a duplicate candidate or an existing same-title draft;
- a mandatory platform declaration that conflicts with the recorded user choice;
- a review, public, schedule, delete, or submit action;
- a field that cannot be read back unambiguously;
- the user says stop, says the upload is already complete, or changes the plan.

Platform-generated tags, temporary title probes, and default AI declarations
are suggestions or controls requiring explicit user review. Never accept them
just to make the page progress.

## Recovery notes

Keep the browser control plane stable: do not alternate between an in-app
browser and Chrome, do not rediscover the same target after every action, and
do not treat an expired connector as a media-transfer failure. Save the exact
failure stage and resume from that stage. A user correction always supersedes
an older plan.

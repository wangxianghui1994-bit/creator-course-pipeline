# v0.2.0

## Optional source provenance

- Added a provider-neutral `source_provenance` metadata contract.
- Added NotebookLM-specific safeguards for captured snapshots, citations, and
  human review.
- Rejected private URLs, absolute paths, traversal paths, and secret-like
  references from public package metadata.
- Documented the boundary between public validation and a private
  NotebookLM/Obsidian trace workflow.

This release still does not connect to NotebookLM, upload content, publish,
schedule, delete, comment, or automate browser pages.

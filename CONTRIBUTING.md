# Contributing

Contributions should keep the repository generic and inspectable.

1. Create a branch from `main`.
2. Add a failing test for behavior changes before implementation.
3. Run `python -X utf8 -m pytest -q` and the layout/privacy checks.
4. Use synthetic media or tiny fixtures; do not add real course files.
5. Explain any platform behavior as observed, documented, or inferred.

Pull requests must not contain API keys, cookies, account identifiers, private
absolute paths, real media, cloned voices, screenshots, draft IDs, or logs that
could reveal them.

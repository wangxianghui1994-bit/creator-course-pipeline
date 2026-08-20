# AiToEarn boundary

The public client is deliberately narrower than the platform's complete
workflow. It uses `X-Api-Key` and fixed GET paths only. The API key must be
provided as `AITOEARN_API_KEY` in the process environment; it is never a CLI
argument, file value, or log value.

The client does not guess upload payload fields or implement the write chain
(`content`, `overrides`, `option`, signed upload, asset confirmation, or Flow
creation). Use the official AiToEarn documentation for the current platform
workflow, then keep any user-authorized browser submission outside this public
Skill.

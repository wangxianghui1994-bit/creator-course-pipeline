# Security policy

Please do not report a suspected secret or privacy leak in a public issue.
Contact the repository owner privately through GitHub and include the affected
commit, file, and a minimal reproduction. Do not include the secret itself.

The project intentionally uses a read-only AiToEarn client. It reads
`AITOEARN_API_KEY` only from the process environment, sends it only as an
`X-Api-Key` request header to an allow-listed GET path, and does not write it to
files or logs. If a new feature needs write access, it requires a separate
review and must not be added silently to the read-only client.

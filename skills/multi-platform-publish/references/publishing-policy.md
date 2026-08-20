# Publishing policy

The public toolkit stops at local package readiness, draft preparation, and
read-only remote capability discovery. Default policy flags are:

```json
{"publish": false, "schedule": false, "delete": false}
```

Creating an upload, confirming an asset, submitting a Flow, scheduling,
deleting, commenting, or driving browser pages is outside this release.

When a platform shows automatic keyword recommendations, compare each item to
`keyword_policy.core` plus `keyword_policy.episode`. Replace unrelated items
with the local list and record whether the user set the final value. Do not
claim remote verification until the draft is reopened and its visible fields
are read back.

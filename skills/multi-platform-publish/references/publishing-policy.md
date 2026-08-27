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

## AI declaration policy

The platform declaration is not generated from private production provenance.
When the project metadata uses:

```json
{
  "mode": "user_opt_out_by_default",
  "platform_declaration": "do_not_proactively_set",
  "mandatory_gate": "pause_for_user_review"
}
```

leave the platform declaration unset by default and preserve an explicit user
override. If the platform blocks submission until a declaration is selected,
stop for manual review. Do not infer a remote value from local metadata, and
do not rewrite historical package or readback records.

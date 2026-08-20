# Package contract

An episode package contains:

- `master-16x9.mp4` and `douyin-9x16.mp4` with H.264 video, AAC audio, and a
  positive duration;
- `cover-bilibili-1146x717.png`, `cover-youtube-1280x720.png`, and
  `cover-douyin-1080x1920.png` with the dimensions in their names;
- `subtitles-zh-Hans.srt`;
- `metadata.json`, `qa-report.json`, `publish-manifest.json`, and
  `publish-state.json`.

`publish-manifest.json` should use the following shape:

```json
{
  "files": {"master": "master-16x9.mp4"},
  "asset_sha256": {"master": "<64 hexadecimal characters>"}
}
```

Every file listed under `files` needs a matching SHA-256 value. Relative paths
only are accepted. The package checker also supports the legacy `assets` and
`source_sha256` forms for migration, but new packages should use `files`.

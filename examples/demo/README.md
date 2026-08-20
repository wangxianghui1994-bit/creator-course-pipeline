# Synthetic demo

Run this from the repository root:

```powershell
python scripts/create_demo_assets.py --output examples/demo/generated
python skills/course-production-pipeline/scripts/validate_episode_package.py examples/demo/generated/EP00-demo
python skills/course-production-pipeline/scripts/validate_skill_chain.py `
  --package-dir examples/demo/generated/EP00-demo `
  --registry examples/demo/generated/registry.json
```

The generator creates a solid-color source video, a sine-wave audio track,
plain subtitles, and solid-color PNG covers. It does not download or embed
copyrighted media and it does not contact any platform.

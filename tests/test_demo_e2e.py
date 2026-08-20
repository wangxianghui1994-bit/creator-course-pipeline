import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is required")
def test_synthetic_media_passes_full_chain(tmp_path):
    generator = load(ROOT / "scripts" / "create_demo_assets.py", "demo_generator")
    package = generator.build_demo(tmp_path / "generated")
    chain = load(
        ROOT / "skills" / "course-production-pipeline" / "scripts" / "validate_skill_chain.py",
        "demo_chain_validator",
    )
    result = chain.validate_chain(package, package.parent / "registry.json")
    assert result["ok"], result
    state_path = package / "publish-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["status"] = "scheduled"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    blocked = chain.validate_chain(package, package.parent / "registry.json")
    assert not blocked["ok"]
    assert any("safe draft boundary" in error for error in blocked["errors"])


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is required")
def test_media_probe_rejects_video_without_audio_and_wrong_cover_size(tmp_path):
    generator = load(ROOT / "scripts" / "create_demo_assets.py", "demo_generator_negative")
    package = generator.build_demo(tmp_path / "generated")
    broken_video = tmp_path / "no-audio.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i",
         str(package / "master-16x9.mp4"), "-an", "-c:v", "copy", str(broken_video)],
        check=True,
    )
    shutil.copy2(broken_video, package / "master-16x9.mp4")
    wrong_cover = tmp_path / "wrong-cover.png"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", "color=c=black:s=10x10", "-frames:v", "1", str(wrong_cover)],
        check=True,
    )
    shutil.copy2(wrong_cover, package / "cover-youtube-1280x720.png")
    validator = load(
        ROOT / "skills" / "course-production-pipeline" / "scripts" / "validate_episode_package.py",
        "negative_package_validator",
    )
    result = validator.validate_episode(package, skip_hash=True)
    assert not result["ok"]
    assert any("audio stream" in error for error in result["errors"])
    assert any("cover-youtube" in error for error in result["errors"])

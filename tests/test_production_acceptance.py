import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "course-production-pipeline" / "scripts" / "validate_episode_package.py"


def load_module():
    spec = importlib.util.spec_from_file_location("production_acceptance", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_v12_metadata(mode="light_music"):
    audio = {
        "background_mode": mode,
        "mix_reviewed": True,
        "speech_intelligibility_reviewed": True,
    }
    if mode == "light_music":
        audio.update({"background_asset_id": "background_audio", "rights_status": "cleared"})
    else:
        audio["reason"] = "deliberate voice-only lesson"
    return {
        "package_schema_version": "1.2",
        "audio_design": audio,
        "cover_profiles": [
            {"id": "bilibili-landscape", "platform": "bilibili", "filename": "cover-bilibili.png", "width": 1146, "height": 717, "source": "dedicated_layout"},
            {"id": "youtube-landscape", "platform": "youtube", "filename": "cover-youtube.png", "width": 1280, "height": 720, "source": "dedicated_layout"},
            {"id": "douyin-landscape", "platform": "douyin", "filename": "cover-douyin-landscape.png", "width": 1440, "height": 1080, "source": "dedicated_layout"},
            {"id": "douyin-portrait", "platform": "douyin", "filename": "cover-douyin-portrait.png", "width": 1080, "height": 1440, "source": "dedicated_layout"},
        ],
    }


def valid_v12_qa():
    return {
        "subtitle_acceptance": {
            "timing_source": "word_alignment",
            "semantic_segmentation": True,
            "proper_nouns_reviewed": True,
            "landscape_safe_area_reviewed": True,
            "vertical_safe_area_reviewed": True,
            "full_listen_reviewed": True,
        }
    }


def valid_manifest():
    return {
        "files": {"background_audio": "background-audio.wav"},
        "asset_sha256": {"background_audio": "A" * 64},
    }


def test_v12_production_acceptance_passes_with_light_music_and_safe_covers():
    module = load_module()
    result = module.validate_production_acceptance(
        valid_v12_metadata(), valid_manifest(), valid_v12_qa()
    )
    assert result["ok"], result


def test_background_sound_omission_is_rejected():
    module = load_module()
    metadata = valid_v12_metadata()
    del metadata["audio_design"]
    result = module.validate_production_acceptance(metadata, valid_manifest(), valid_v12_qa())
    assert not result["ok"]
    assert any("audio_design" in error for error in result["errors"])


def test_intentional_none_requires_reason_and_review():
    module = load_module()
    metadata = valid_v12_metadata(mode="intentional_none")
    metadata["audio_design"].pop("reason")
    result = module.validate_production_acceptance(metadata, valid_manifest(), valid_v12_qa())
    assert not result["ok"]
    assert any("reason" in error for error in result["errors"])


def test_missing_audio_asset_rights_or_mix_review_is_rejected():
    module = load_module()
    metadata = valid_v12_metadata()
    metadata["audio_design"]["rights_status"] = "unknown"
    qa = valid_v12_qa()
    qa["subtitle_acceptance"]["full_listen_reviewed"] = False
    metadata["audio_design"]["mix_reviewed"] = False
    result = module.validate_production_acceptance(metadata, valid_manifest(), qa)
    assert not result["ok"]
    assert any("rights" in error for error in result["errors"])
    assert any("mix" in error for error in result["errors"])


def test_subtitle_acceptance_requires_word_alignment_and_both_safe_areas():
    module = load_module()
    qa = valid_v12_qa()
    qa["subtitle_acceptance"]["timing_source"] = "fixed_character_split"
    qa["subtitle_acceptance"]["vertical_safe_area_reviewed"] = False
    result = module.validate_production_acceptance(valid_v12_metadata(), valid_manifest(), qa)
    assert not result["ok"]
    assert any("timing_source" in error for error in result["errors"])
    assert any("vertical" in error for error in result["errors"])


def test_cover_profiles_reject_screenshot_and_legacy_douyin_ratio():
    module = load_module()
    metadata = valid_v12_metadata()
    metadata["cover_profiles"][-1]["source"] = "video_screenshot"
    metadata["cover_profiles"][-1]["width"] = 1080
    metadata["cover_profiles"][-1]["height"] = 1920
    result = module.validate_production_acceptance(metadata, valid_manifest(), valid_v12_qa())
    assert not result["ok"]
    assert any("dedicated" in error or "cover" in error for error in result["errors"])


def test_legacy_schema_remains_accepted_with_warning():
    module = load_module()
    result = module.validate_production_acceptance({}, {}, {})
    assert result["ok"], result
    assert any("legacy" in warning for warning in result["warnings"])

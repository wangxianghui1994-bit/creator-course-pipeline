import importlib.util


ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "course-production-pipeline" / "scripts" / "validate_timing_contract.py"


def load_module():
    spec = importlib.util.spec_from_file_location("timing_contract", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_alignment():
    return {
        "timing_source": "local_word_alignment",
        "canonical_script": "先确认方向再开始行动",
        "word_timestamps": [{"char": "先", "start": 0, "end": 0.2}],
        "subtitle_policy": {"mode": "semantic_phrase", "max_characters": 16},
        "semantic_cues": [
            {"text": "先确认方向", "start": 0, "end": 1},
            {"text": "再开始行动", "start": 1, "end": 2},
        ],
    }


def valid_scenes():
    return {
        "timing_source": "local_word_alignment",
        "beats": [
            {
                "beat_id": "B01",
                "start": 0,
                "end": 2,
                "spoken_anchor": "确认方向",
                "anchor_start": 0.2,
                "anchor_end": 0.8,
            }
        ],
    }


def test_semantic_alignment_and_spoken_anchor_pass():
    module = load_module()
    result = module.validate_timing_contract(valid_alignment(), valid_scenes())
    assert result["ok"], result


def test_fixed_character_timing_is_rejected():
    module = load_module()
    alignment = valid_alignment()
    alignment["timing_source"] = "fixed_character_split"
    result = module.validate_timing_contract(alignment)
    assert not result["ok"]
    assert any("preview-only" in error for error in result["errors"])


def test_cue_text_must_cover_canonical_script():
    module = load_module()
    alignment = valid_alignment()
    alignment["semantic_cues"][1]["text"] = "再开始"
    result = module.validate_timing_contract(alignment)
    assert not result["ok"]
    assert any("canonical_script" in error for error in result["errors"])


def test_overlapping_beat_and_missing_anchor_are_rejected():
    module = load_module()
    scenes = valid_scenes()
    scenes["beats"].append(
        {
            "beat_id": "B02",
            "start": 1.5,
            "end": 3,
            "spoken_anchor": "不存在的词",
            "anchor_start": 1.5,
            "anchor_end": 2,
        }
    )
    result = module.validate_timing_contract(valid_alignment(), scenes)
    assert not result["ok"]
    assert any("overlaps" in error for error in result["errors"])
    assert any("absent" in error for error in result["errors"])

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "skills" / "multi-platform-publish" / "references" / "browser-draft-handoff.md"


def reference_text():
    assert REFERENCE.is_file()
    return REFERENCE.read_text(encoding="utf-8").lower()


def test_browser_contract_has_explicit_state_boundaries():
    text = reference_text()
    for state in ("uploading", "uploaded_draft", "draft_saved", "remote_verified"):
        assert state in text
    assert "upload bar" in text or "上传进度" in text


def test_browser_contract_prevents_control_plane_churn():
    text = reference_text()
    for phrase in ("one task", "existing tab", "condition", "two authorization", "manual file"):
        assert phrase in text


def test_browser_contract_halts_on_duplicates_mandatory_fields_and_user_stop():
    text = reference_text()
    for phrase in ("duplicate", "mandatory", "user says stop", "public", "schedule", "delete"):
        assert phrase in text

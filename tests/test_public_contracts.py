import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COURSE_SCRIPTS = ROOT / "skills" / "course-production-pipeline" / "scripts"
PUBLISH_SCRIPTS = ROOT / "skills" / "multi-platform-publish" / "scripts"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_metadata(core=None):
    core = core or ["alpha", "beta"]
    allowed = core + ["episode-topic", "decision"]
    return {
        "keyword_policy": {
            "core": core,
            "episode": ["episode-topic", "decision"],
            "reject_unlisted": True,
        },
        "douyin": {"keywords": allowed, "hashtags": allowed},
        "bilibili": {"tags": allowed},
        "youtube": {"tags": allowed},
    }


def test_keyword_policy_uses_metadata_defined_core_and_rejects_unlisted():
    module = load_module(
        PUBLISH_SCRIPTS / "validate_publish_metadata.py", "public_metadata_validator"
    )
    assert module.validate_metadata(valid_metadata())["ok"]
    broken = valid_metadata()
    broken["douyin"]["keywords"].append("美食探店")
    result = module.validate_metadata(broken)
    assert not result["ok"]
    assert any("unlisted" in error for error in result["errors"])


def test_keyword_policy_reports_empty_duplicate_and_order_errors():
    module = load_module(
        PUBLISH_SCRIPTS / "validate_publish_metadata.py", "public_metadata_validator_errors"
    )
    broken = valid_metadata(core=["beta", "alpha"])
    broken["keyword_policy"]["core"] = ["alpha", "alpha"]
    broken["douyin"]["keywords"] = ["beta", "alpha", "alpha", "episode-topic", "decision"]
    result = module.validate_metadata(broken)
    assert not result["ok"]
    assert any("duplicate" in error for error in result["errors"])
    empty = valid_metadata()
    empty["keyword_policy"]["core"] = []
    assert not module.validate_metadata(empty)["ok"]


def test_state_validator_accepts_draft_but_chain_blocks_public_states():
    state_module = load_module(
        PUBLISH_SCRIPTS / "validate_publish_state.py", "public_state_validator"
    )
    state = {
        "status": "draft_saved",
        "subtitle_policy": "do not upload subtitles",
        "platforms": {
            name: {"status": "draft_saved", "public_url": None, "last_verified_at": "2026-01-01T00:00:00Z"}
            for name in ("douyin", "bilibili", "youtube")
        },
    }
    assert state_module.validate_state(state)["ok"]
    chain_module = load_module(
        COURSE_SCRIPTS / "validate_skill_chain.py", "public_chain_validator"
    )
    state["status"] = "scheduled"
    assert not chain_module.is_safe_draft_state(state)


def test_package_validator_rejects_traversal_and_checks_every_manifest_asset(tmp_path):
    module = load_module(
        COURSE_SCRIPTS / "validate_episode_package.py", "public_package_validator"
    )
    package = tmp_path / "package"
    package.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    manifest = {
        "files": {"notes": "../outside.txt"},
        "asset_sha256": {"notes": "BAD"},
    }
    for name, payload in {
        "metadata.json": valid_metadata(),
        "qa-report.json": {"status": "pass", "manifest_hashes_match": True},
        "publish-manifest.json": manifest,
        "publish-state.json": {"status": "package_ready", "platforms": {}},
    }.items():
        (package / name).write_text(json.dumps(payload), encoding="utf-8")
    result = module.validate_episode(package, skip_media_probe=True)
    assert not result["ok"]
    assert any("outside" in error or "travers" in error for error in result["errors"])


def test_aitoearn_client_has_only_whitelisted_get_operations(monkeypatch):
    module = load_module(
        PUBLISH_SCRIPTS / "aitoearn_readonly.py", "public_aitoearn_client"
    )
    monkeypatch.setenv("AITOEARN_API_KEY", "test-secret-key")
    client = module.AiToEarnReadOnlyClient(transport=lambda method, path, params: {"code": 0})
    assert client.call("platforms")["code"] == 0
    try:
        client.request("POST", "/api/v2/channels/platforms")
    except ValueError as exc:
        assert "GET" in str(exc)
    else:
        raise AssertionError("non-GET operation was accepted")


def test_installer_defaults_to_preview_and_requires_apply(tmp_path):
    script = ROOT / "scripts" / "install_skills.py"
    result = subprocess.run(
        [sys.executable, str(script), "--target", str(tmp_path / "skills")],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "skills").exists()
    assert "preview" in result.stdout.lower()


def test_installer_backs_up_existing_skill_before_apply(tmp_path):
    script = ROOT / "scripts" / "install_skills.py"
    target = tmp_path / "skills"
    existing = target / "course-production-pipeline"
    existing.mkdir(parents=True)
    (existing / "old.txt").write_text("old", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script), "--target", str(target), "--apply"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (target / "course-production-pipeline" / "SKILL.md").is_file()
    backups = list((tmp_path / "creator-course-pipeline-backups").rglob("old.txt"))
    assert backups and backups[0].read_text(encoding="utf-8") == "old"


def test_skill_layout_and_public_tree_scans_pass():
    layout = load_module(ROOT / "scripts" / "validate_skill_layout.py", "layout_validator")
    privacy = load_module(ROOT / "scripts" / "scan_public_tree.py", "privacy_scanner")
    assert layout.validate() == []
    assert privacy.scan() == []

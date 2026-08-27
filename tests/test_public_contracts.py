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
        "disclosure_policy": {
            "mode": "user_opt_out_by_default",
            "platform_declaration": "do_not_proactively_set",
            "mandatory_gate": "pause_for_user_review",
        },
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


def test_disclosure_policy_is_validated_and_does_not_fill_platform_fields():
    module = load_module(
        PUBLISH_SCRIPTS / "validate_publish_metadata.py", "public_disclosure_policy"
    )
    result = module.validate_metadata(valid_metadata())
    assert result["ok"], result
    assert any("disclosure policy" in check for check in result["checks"])
    broken = valid_metadata()
    broken["disclosure_policy"]["mode"] = "always_disclose"
    result = module.validate_metadata(broken)
    assert not result["ok"]
    assert any("disclosure_policy.mode" in error for error in result["errors"])


def test_source_provenance_is_optional_and_accepts_a_reviewed_notebooklm_source():
    module = load_module(
        COURSE_SCRIPTS / "source_provenance.py", "public_source_provenance_optional"
    )
    metadata = valid_metadata()
    assert module.validate_source_provenance(metadata)["ok"]
    metadata["source_provenance"] = {
        "source_type": "notebooklm",
        "source_ref": "notebooklm-course-research-001",
        "snapshot_status": "captured",
        "citation_count": 3,
        "user_reviewed": True,
    }
    result = module.validate_source_provenance(metadata)
    assert result["ok"], result
    assert any("notebooklm" in check.lower() for check in result["checks"])


def test_notebooklm_provenance_requires_snapshot_and_human_review():
    module = load_module(
        COURSE_SCRIPTS / "source_provenance.py", "public_source_provenance_rules"
    )
    metadata = valid_metadata()
    metadata["source_provenance"] = {
        "source_type": "notebooklm",
        "source_ref": "notebooklm-course-research-001",
        "snapshot_status": "not_captured",
        "citation_count": 0,
        "user_reviewed": False,
    }
    result = module.validate_source_provenance(metadata)
    assert not result["ok"]
    assert any("snapshot" in error for error in result["errors"])
    assert any("review" in error for error in result["errors"])


def test_source_provenance_rejects_private_urls_and_secret_like_references():
    module = load_module(
        COURSE_SCRIPTS / "source_provenance.py", "public_source_provenance_safety"
    )
    metadata = valid_metadata()
    metadata["source_provenance"] = {
        "source_type": "notebooklm",
        "source_ref": "https://notebooklm.google.com/notebook/private?access_" + "token=secret",
        "snapshot_status": "captured",
        "citation_count": 1,
        "user_reviewed": True,
    }
    result = module.validate_source_provenance(metadata)
    assert not result["ok"]
    assert any("private" in error or "secret" in error for error in result["errors"])


def test_public_notebooklm_example_uses_the_sanitized_contract():
    module = load_module(
        COURSE_SCRIPTS / "source_provenance.py", "public_source_provenance_example"
    )
    example = json.loads(
        (ROOT / "examples" / "yangming-course" / "source-provenance.example.json")
        .read_text(encoding="utf-8")
    )
    result = module.validate_source_provenance(example)
    assert result["ok"], result


def test_package_validator_checks_declared_source_provenance(tmp_path):
    module = load_module(
        COURSE_SCRIPTS / "validate_episode_package.py", "public_package_source_validator"
    )
    package = tmp_path / "package"
    package.mkdir()
    metadata = valid_metadata()
    metadata["source_provenance"] = {
        "source_type": "notebooklm",
        "source_ref": "notebooklm-course-research-001",
        "snapshot_status": "not_captured",
        "citation_count": 0,
        "user_reviewed": False,
    }
    for name, payload in {
        "metadata.json": metadata,
        "qa-report.json": {"status": "pass", "manifest_hashes_match": True},
        "publish-manifest.json": {"files": {}, "asset_sha256": {}},
        "publish-state.json": {"status": "package_ready", "platforms": {}},
    }.items():
        (package / name).write_text(json.dumps(payload), encoding="utf-8")
    result = module.validate_episode(package, skip_media_probe=True)
    assert any("source provenance" in error for error in result["errors"])


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
    assert not list(target.rglob("__pycache__"))
    backups = list((tmp_path / "creator-course-pipeline-backups").rglob("old.txt"))
    assert backups and backups[0].read_text(encoding="utf-8") == "old"


def test_skill_layout_and_public_tree_scans_pass():
    layout = load_module(ROOT / "scripts" / "validate_skill_layout.py", "layout_validator")
    privacy = load_module(ROOT / "scripts" / "scan_public_tree.py", "privacy_scanner")
    assert layout.validate() == []
    assert privacy.scan() == []

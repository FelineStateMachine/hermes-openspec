import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import tools
import registry
from dashboard import plugin_api


def test_openspec_instructions_accepts_spec_alias_without_changes(tmp_path):
    exe = tools._openspec_bin()
    if not exe:
        pytest.skip("openspec CLI is not available")

    subprocess.run([exe, "init", "--tools", "none", str(tmp_path)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    result = json.loads(tools.openspec_instructions({"workdir": str(tmp_path), "artifact": "spec"}))

    assert result["ok"] is True
    assert result["stdout"]["artifact"] == "specs"
    assert result["stdout"]["fallback"] == "template"
    assert "## ADDED Requirements" in result["stdout"]["content"]
    assert "No changes found" in result["stdout"]["reason"]


def test_dashboard_init_layout_ensures_plugin_supported_directories(tmp_path):
    openspec_root = tmp_path / "openspec"
    (openspec_root / "changes").mkdir(parents=True)
    (openspec_root / "specs").mkdir()

    plugin_api._ensure_openspec_layout(tmp_path)

    assert (openspec_root / "changes").is_dir()
    assert (openspec_root / "changes" / "archive").is_dir()
    assert (openspec_root / "specs").is_dir()
    assert (openspec_root / "ideas").is_dir()


def test_dashboard_init_fallback_layout_matches_supported_scan_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(plugin_api, "_find_openspec_bin", lambda: None)
    source = {"token": "os_test", "id": "os_test", "name": "demo", "path": str(tmp_path), "created_at": 0}

    class FakeRegistry:
        def get_source(self, source_id):
            return source if source_id == "os_test" else None

    monkeypatch.setattr(plugin_api, "_registry", FakeRegistry())

    response = plugin_api.init_source("os_test")

    assert response["ok"] is True
    openspec_root = tmp_path / "openspec"
    assert (openspec_root / "changes").is_dir()
    assert (openspec_root / "changes" / "archive").is_dir()
    assert (openspec_root / "specs").is_dir()
    assert (openspec_root / "ideas").is_dir()
    assert response["source"]["valid"] is True


def test_registry_change_sequence_appends_and_preserves_existing_positions(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "db_path", lambda: tmp_path / "openspec.db")

    first = registry.ensure_change_sequence("os_test", ["second", "first"])
    assert first["second"]["position"] == 1
    assert first["first"]["position"] == 2

    second = registry.ensure_change_sequence("os_test", ["first", "third", "second"])
    assert second["second"]["position"] == 1
    assert second["first"]["position"] == 2
    assert second["third"]["position"] == 3


def test_dashboard_scan_attaches_sequence_without_openspec_files(tmp_path, monkeypatch):
    openspec_root = tmp_path / "openspec" / "changes"
    for name in ["alpha", "beta"]:
        change_dir = openspec_root / name
        change_dir.mkdir(parents=True)
        (change_dir / "proposal.md").write_text(f"# {name.title()}\n", encoding="utf-8")

    class FakeRegistry:
        def change_token(self, name):
            return "os_" + name

        def ensure_change_sequence(self, source_id, names):
            assert source_id == "os_test"
            return {name: {"position": i + 1, "firstSeenAt": 1.0, "updatedAt": 1.0} for i, name in enumerate(names)}

    monkeypatch.setattr(plugin_api, "_registry", FakeRegistry())
    payload = plugin_api._scan(tmp_path, "os_test")

    assert payload is not None
    assert [ch["name"] for ch in payload["changes"]] == ["alpha", "beta"]
    assert [ch["sequence"]["position"] for ch in payload["changes"]] == [1, 2]
    assert not (openspec_root / "alpha" / ".sequence").exists()


def test_change_sequence_tool_declares_order_and_dependencies(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "db_path", lambda: tmp_path / "openspec.db")
    monkeypatch.setattr(tools, "_registry_module", lambda: registry)
    project = tmp_path / "project"
    changes_root = project / "openspec" / "changes"
    names = ["phase-one", "phase-two", "final-proof"]
    for name in names:
        change_dir = changes_root / name
        change_dir.mkdir(parents=True)
        (change_dir / "proposal.md").write_text(f"# {name}\n", encoding="utf-8")
    registry.add_source(str(project), "demo")

    result = json.loads(tools.openspec_change_sequence_set({
        "identifier": "demo",
        "changes": names,
        "group_id": "poc",
        "dependencies": {"final-proof": ["phase-one", "phase-two"]},
    }))

    assert result["ok"] is True
    assert [item["name"] for item in result["changes"]] == names
    assert result["changes"][0]["sequence"]["position"] == 1
    assert result["changes"][2]["sequence"]["groupId"] == "poc"
    assert result["changes"][2]["sequence"]["dependsOn"] == ["phase-one", "phase-two"]
    assert not (changes_root / "final-proof" / ".sequence").exists()

    context = json.loads(tools.openspec_context({"identifier": "demo"}))
    final = next(item for item in context["changes"] if item["name"] == "final-proof")
    assert final["sequence"]["dependsOn"] == ["phase-one", "phase-two"]

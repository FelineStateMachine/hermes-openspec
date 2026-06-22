import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import tools
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

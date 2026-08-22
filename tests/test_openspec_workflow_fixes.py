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


def test_title_from_markdown_prefers_closed_frontmatter_title(tmp_path):
    path = tmp_path / "proposal.md"
    path.write_text(
        "---\n"
        "title: Human-readable title\n"
        "created: 2026-08-21\n"
        "---\n"
        "# Heading fallback\n",
        encoding="utf-8",
    )

    assert plugin_api._title_from_markdown(path, "change-id") == "Human-readable title"


def test_title_from_markdown_uses_h1_without_frontmatter(tmp_path):
    path = tmp_path / "proposal.md"
    path.write_text("# Heading title\n\nBody\n", encoding="utf-8")

    assert plugin_api._title_from_markdown(path, "change-id") == "Heading title"


def test_title_from_markdown_uses_identifier_without_title_or_h1(tmp_path):
    path = tmp_path / "proposal.md"
    path.write_text("Body without a title\n", encoding="utf-8")

    assert plugin_api._title_from_markdown(path, "change-id") == "change-id"


def test_title_from_markdown_ignores_nonleading_frontmatter_looking_block(tmp_path):
    path = tmp_path / "proposal.md"
    path.write_text(
        "# Real heading\n"
        "\n"
        "---\n"
        "title: Not metadata\n"
        "---\n",
        encoding="utf-8",
    )

    assert plugin_api._title_from_markdown(path, "change-id") == "Real heading"


def test_title_from_markdown_falls_back_after_unclosed_frontmatter(tmp_path):
    path = tmp_path / "proposal.md"
    path.write_text(
        "---\n"
        "title: Unusable because the block is unclosed\n"
        "# Heading fallback\n",
        encoding="utf-8",
    )

    assert plugin_api._title_from_markdown(path, "change-id") == "Heading fallback"


def test_change_summary_exposes_frontmatter_title(tmp_path):
    change_dir = tmp_path / "change-id"
    change_dir.mkdir()
    (change_dir / "proposal.md").write_text(
        "---\n"
        "title: Change summary title\n"
        "---\n"
        "## Summary\n",
        encoding="utf-8",
    )

    summary = plugin_api._change_summary(change_dir, "ivault")

    assert summary is not None
    assert summary["title"] == "Change summary title"


def test_idea_summary_exposes_frontmatter_title(tmp_path):
    idea_path = tmp_path / "idea-id.md"
    idea_path.write_text(
        "---\n"
        "title: Idea summary title\n"
        "---\n"
        "## Summary\n",
        encoding="utf-8",
    )

    summary = plugin_api._idea_summary(idea_path, "ivault")

    assert summary is not None
    assert summary["title"] == "Idea summary title"


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


# ---------------------------------------------------------------------------
# Idea resolution (ivault/os_fd3445 tasks 1.3): openspec_context must list and
# resolve registered idea references using the same source-qualified shape as
# changes, and must fail explicitly on cross-kind token ambiguity.
# ---------------------------------------------------------------------------


def _register_demo_source(tmp_path, monkeypatch):
    """Isolate registry DB to tmp and point tools at the real registry module."""
    monkeypatch.setattr(registry, "db_path", lambda: tmp_path / "openspec.db")
    monkeypatch.setattr(tools, "_registry_module", lambda: registry)
    registry.add_source(str(tmp_path), "demo")


def _write_idea(tmp_path, stem: str, body: str = "Idea body text"):
    ideas_root = tmp_path / "openspec" / "ideas"
    ideas_root.mkdir(parents=True, exist_ok=True)
    idea_file = ideas_root / f"{stem}.md"
    idea_file.write_text(f"---\ntitle: {stem.title()}\n---\n{body}\n", encoding="utf-8")
    return idea_file


def test_openspec_context_lists_ideas_for_bare_source(tmp_path, monkeypatch):
    _register_demo_source(tmp_path, monkeypatch)
    _write_idea(tmp_path, "hermes-agentmail-inbox-integration")

    result = json.loads(tools.openspec_context({"identifier": "demo"}))

    assert result["ok"] is True
    ideas = result["ideas"]
    assert len(ideas) == 1
    idea = ideas[0]
    assert idea["name"] == "hermes-agentmail-inbox-integration"
    assert idea["filename"] == "hermes-agentmail-inbox-integration.md"
    assert idea["token"] == "os_1655dd"


def test_openspec_context_resolves_idea_by_token(tmp_path, monkeypatch):
    _register_demo_source(tmp_path, monkeypatch)
    _write_idea(tmp_path, "hermes-agentmail-inbox-integration")

    result = json.loads(tools.openspec_context({"identifier": "demo/os_1655dd"}))

    assert result["ok"] is True
    idea = result["idea"]
    assert idea["name"] == "hermes-agentmail-inbox-integration"
    assert idea["filename"] == "hermes-agentmail-inbox-integration.md"
    assert idea["token"] == "os_1655dd"
    assert "Idea body text" in idea["content"]


def test_openspec_context_resolves_idea_by_literal_stem(tmp_path, monkeypatch):
    _register_demo_source(tmp_path, monkeypatch)
    _write_idea(tmp_path, "hermes-agentmail-inbox-integration")

    result = json.loads(
        tools.openspec_context({"identifier": "demo/hermes-agentmail-inbox-integration"})
    )

    assert result["ok"] is True
    idea = result["idea"]
    assert idea["name"] == "hermes-agentmail-inbox-integration"
    assert idea["filename"] == "hermes-agentmail-inbox-integration.md"
    assert idea["token"] == "os_1655dd"


def test_openspec_context_reports_cross_kind_ambiguity(tmp_path, monkeypatch):
    _register_demo_source(tmp_path, monkeypatch)
    # Change folder and idea file share the same stem → identical derived token.
    change_dir = tmp_path / "openspec" / "changes" / "same-artifact"
    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text("# Same Artifact\n", encoding="utf-8")
    _write_idea(tmp_path, "same-artifact")
    token = registry.change_token("same-artifact")

    result = json.loads(tools.openspec_context({"identifier": f"demo/{token}"}))

    assert result["ok"] is False
    error = result["error"].lower()
    assert "ambiguous" in error
    for kind in ("change", "spec", "idea"):
        assert kind in error

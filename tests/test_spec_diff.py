"""Tests for the semantic spec diff parser, diff function, and agent tool."""

import json
import sys
from pathlib import Path

import pytest

# Make the repo root importable
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))

import spec_parser
import tools


# ─── Parser tests ───────────────────────────────────────────────────────


SAMPLE_SPEC = """# Agent Tools Specification

## Purpose

Tools for agents to interact with OpenSpec.

## Requirements

### Requirement: Context resolution
Resolve identifiers into repo paths.

#### Scenario: Resolve a source name
- **GIVEN** a source is registered
- **WHEN** an agent calls context
- **THEN** the tool returns the repo path

#### Scenario: Resolve a change token
- **GIVEN** a change exists
- **WHEN** an agent calls context with a token
- **THEN** the tool returns the change content

### Requirement: Validation
Validate artifacts.

#### Scenario: Validate a change
- **WHEN** an agent calls validate
- **THEN** the tool returns validation errors
"""


def test_parse_spec_well_formed():
    result = spec_parser.parse_spec(SAMPLE_SPEC)
    assert result["title"] == "Agent Tools"
    assert "Tools for agents" in result["purpose"]
    assert len(result["requirements"]) == 2

    req1 = result["requirements"][0]
    assert req1["name"] == "Context resolution"
    assert "Resolve identifiers" in req1["description"]
    assert len(req1["scenarios"]) == 2

    scn1 = req1["scenarios"][0]
    assert scn1["name"] == "Resolve a source name"
    assert len(scn1["steps"]) == 3
    assert scn1["steps"][0]["type"] == "GIVEN"
    assert scn1["steps"][0]["text"] == "a source is registered"


def test_parse_spec_no_requirements():
    md = "# Title\n\n## Purpose\n\nSome purpose text.\n"
    result = spec_parser.parse_spec(md)
    assert result["title"] == "Title"
    assert result["purpose"] == "Some purpose text."
    assert result["requirements"] == []


def test_parse_spec_empty():
    result = spec_parser.parse_spec("")
    assert result == {"title": "", "purpose": "", "requirements": []}


def test_parse_spec_none():
    result = spec_parser.parse_spec(None)
    assert result == {"title": "", "purpose": "", "requirements": []}


def test_parse_spec_fallback_no_requirements():
    md = "# Title\n\nSome text without requirement headers.\n"
    result = spec_parser.parse_spec(md)
    assert result["title"] == "Title"
    assert result["requirements"] == []


# ─── Semantic diff tests ────────────────────────────────────────────────


def test_diff_added_requirement():
    before = "# S\n## Purpose\nP\n"
    after = "# S\n## Purpose\nP\n### Requirement: New Req\nDesc.\n"
    diff = spec_parser.semantic_spec_diff(before, after)
    assert diff["status"] == "modified"
    assert len(diff["requirements"]["added"]) == 1
    assert diff["requirements"]["added"][0]["name"] == "New Req"


def test_diff_removed_requirement():
    before = "# S\n### Requirement: Old Req\nDesc.\n"
    after = "# S\n"
    diff = spec_parser.semantic_spec_diff(before, after)
    assert diff["status"] == "modified"
    assert len(diff["requirements"]["removed"]) == 1
    assert diff["requirements"]["removed"][0]["name"] == "Old Req"


def test_diff_modified_requirement_description():
    before = "# S\n### Requirement: Req A\nOld description.\n"
    after = "# S\n### Requirement: Req A\nNew description.\n"
    diff = spec_parser.semantic_spec_diff(before, after)
    assert diff["status"] == "modified"
    assert len(diff["requirements"]["modified"]) == 1
    mod = diff["requirements"]["modified"][0]
    assert mod["name"] == "Req A"
    assert mod["before"]["description"] == "Old description."
    assert mod["after"]["description"] == "New description."


def test_diff_scenario_level_delta():
    before = """# S
### Requirement: Req A
Description.

#### Scenario: Scenario 1
- **GIVEN** something
- **THEN** result

#### Scenario: Scenario 2
- **WHEN** action
- **THEN** result2
"""
    after = """# S
### Requirement: Req A
Description.

#### Scenario: Scenario 1
- **GIVEN** something else
- **THEN** result

#### Scenario: Scenario 3
- **WHEN** new action
- **THEN** new result
"""
    diff = spec_parser.semantic_spec_diff(before, after)
    assert diff["status"] == "modified"
    mod = diff["requirements"]["modified"][0]
    assert len(mod["scenarios_added"]) == 1
    assert mod["scenarios_added"][0]["name"] == "Scenario 3"
    assert len(mod["scenarios_modified"]) == 1
    assert mod["scenarios_modified"][0]["name"] == "Scenario 1"
    assert len(mod["scenarios_removed"]) == 1
    assert mod["scenarios_removed"][0]["name"] == "Scenario 2"


def test_diff_unchanged_requirement():
    before = "# S\n### Requirement: Req A\nSame desc.\n"
    after = "# S\n### Requirement: Req A\nSame desc.\n"
    diff = spec_parser.semantic_spec_diff(before, after)
    assert diff["status"] == "unchanged"
    assert "Req A" in diff["requirements"]["unchanged"]


def test_diff_no_baseline():
    before = None
    after = "# S\n### Requirement: Req A\nDesc.\n"
    diff = spec_parser.semantic_spec_diff(before, after)
    assert diff["status"] == "added"
    assert len(diff["requirements"]["added"]) == 1


def test_diff_deleted_spec():
    before = "# S\n### Requirement: Req A\nDesc.\n"
    after = None
    diff = spec_parser.semantic_spec_diff(before, after)
    assert diff["status"] == "deleted"
    assert len(diff["requirements"]["removed"]) == 1


def test_semantic_summary():
    diff = {
        "requirements": {
            "added": [{"name": "A"}, {"name": "B"}],
            "modified": [{"name": "C"}],
            "removed": [],
            "unchanged": ["D"],
        }
    }
    summary = spec_parser.semantic_summary(diff)
    assert summary == {"added": 2, "modified": 1, "removed": 0}


# ─── Tool handler tests ─────────────────────────────────────────────────


@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal OpenSpec project with a baseline spec and a change."""
    openspec = tmp_path / "openspec"
    openspec.mkdir()

    # Baseline spec
    baseline = openspec / "specs" / "agent-tools" / "spec.md"
    baseline.parent.mkdir(parents=True)
    baseline.write_text("""# Agent Tools Specification

## Purpose

Tools for agents.

## Requirements

### Requirement: Context resolution
Resolve identifiers.

#### Scenario: Resolve source
- **GIVEN** a source
- **WHEN** called
- **THEN** returns path

### Requirement: Validation
Validate artifacts.
""")

    # Change spec (adds a requirement, modifies one)
    change_spec = openspec / "changes" / "test-change" / "specs" / "agent-tools" / "spec.md"
    change_spec.parent.mkdir(parents=True)
    change_spec.write_text("""# Agent Tools Specification

## Purpose

Tools for agents.

## Requirements

### Requirement: Context resolution
Resolve identifiers into repo paths and workdir hints.

#### Scenario: Resolve source
- **GIVEN** a source
- **WHEN** called
- **THEN** returns path

### Requirement: Semantic diff
Compare specs at the requirement level.
""")

    # Minimal proposal so the change is valid
    (openspec / "changes" / "test-change" / "proposal.md").write_text("## Why\nTest.\n")

    return tmp_path


def test_tool_diff_change_vs_baseline(tmp_project):
    result = json.loads(tools.openspec_spec_diff({
        "workdir": str(tmp_project),
        "spec": "agent-tools",
        "change": "test-change",
    }))
    assert result["ok"] is True
    assert result["status"] == "modified"
    assert result["baseline_exists"] is True
    reqs = result["requirements"]
    assert len(reqs["added"]) == 1
    assert reqs["added"][0]["name"] == "Semantic diff"
    assert len(reqs["removed"]) == 1
    assert reqs["removed"][0]["name"] == "Validation"
    assert len(reqs["modified"]) == 1
    assert reqs["modified"][0]["name"] == "Context resolution"
    assert "line_diff" in result
    assert result["line_diff"]  # non-empty


def test_tool_new_spec_no_baseline(tmp_project):
    # Create a change with a spec that has no baseline
    change_spec = tmp_project / "openspec" / "changes" / "test-change" / "specs" / "new-spec" / "spec.md"
    change_spec.parent.mkdir(parents=True)
    change_spec.write_text("# New Spec\n### Requirement: New Req\nDesc.\n")

    result = json.loads(tools.openspec_spec_diff({
        "workdir": str(tmp_project),
        "spec": "new-spec",
        "change": "test-change",
    }))
    assert result["ok"] is True
    assert result["status"] == "added"
    assert result["baseline_exists"] is False
    assert len(result["requirements"]["added"]) == 1


def test_tool_missing_change_spec(tmp_project):
    result = json.loads(tools.openspec_spec_diff({
        "workdir": str(tmp_project),
        "spec": "nonexistent",
        "change": "test-change",
    }))
    assert result["ok"] is False
    assert "not found" in result["error"]


def test_tool_missing_spec_no_change(tmp_project):
    result = json.loads(tools.openspec_spec_diff({
        "workdir": str(tmp_project),
        "spec": "nonexistent",
    }))
    assert result["ok"] is False
    assert "not found" in result["error"]


def test_tool_path_traversal(tmp_project):
    result = json.loads(tools.openspec_spec_diff({
        "workdir": str(tmp_project),
        "spec": "../../../etc/passwd",
        "change": "test-change",
    }))
    assert result["ok"] is False
    assert "parent references" in result["error"]


def test_tool_no_spec(tmp_project):
    result = json.loads(tools.openspec_spec_diff({
        "workdir": str(tmp_project),
    }))
    assert result["ok"] is False
    assert "spec is required" in result["error"]

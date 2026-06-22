"""Tests for spec-first-class tools: create, show, list, and serializer round-trip."""

import json
import sys
from pathlib import Path

import pytest

# Ensure the repo root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools
import spec_parser


# ---------------------------------------------------------------------------
# spec_to_markdown serializer
# ---------------------------------------------------------------------------

def test_serializer_produces_valid_spec_markdown():
    requirements = [
        {
            "name": "Create spec",
            "description": "The system SHALL create a spec.",
            "scenarios": [
                {
                    "name": "Happy path",
                    "steps": [
                        {"type": "GIVEN", "text": "a project"},
                        {"type": "WHEN", "text": "an agent creates a spec"},
                        {"type": "THEN", "text": "the spec is written"},
                    ],
                },
            ],
        },
    ]
    md = spec_parser.spec_to_markdown("Test Spec", "Test purpose", requirements)
    assert "# Test Spec" in md
    assert "## Purpose" in md
    assert "Test purpose" in md
    assert "## Requirements" in md
    assert "### Requirement: Create spec" in md
    assert "The system SHALL create a spec." in md
    assert "#### Scenario: Happy path" in md
    assert "- **GIVEN** a project" in md
    assert "- **WHEN** an agent creates a spec" in md
    assert "- **THEN** the spec is written" in md


def test_serializer_round_trip_with_parse_spec():
    """spec_to_markdown output must be parseable by parse_spec back to equivalent structure."""
    original = [
        {
            "name": "Round trip",
            "description": "Description here.",
            "scenarios": [
                {
                    "name": "Scenario A",
                    "steps": [
                        {"type": "GIVEN", "text": "context"},
                        {"type": "WHEN", "text": "action"},
                        {"type": "THEN", "text": "result"},
                    ],
                },
            ],
        },
    ]
    md = spec_parser.spec_to_markdown("Round Trip Spec", "Purpose statement", original)
    parsed = spec_parser.parse_spec(md)

    assert parsed["title"] == "Round Trip Spec"
    assert parsed["purpose"] == "Purpose statement"
    assert len(parsed["requirements"]) == 1
    req = parsed["requirements"][0]
    assert req["name"] == "Round trip"
    assert req["description"] == "Description here."
    assert len(req["scenarios"]) == 1
    scn = req["scenarios"][0]
    assert scn["name"] == "Scenario A"
    assert len(scn["steps"]) == 3
    assert scn["steps"][0]["type"] == "GIVEN"
    assert scn["steps"][0]["text"] == "context"


def test_serializer_handles_empty_requirements():
    md = spec_parser.spec_to_markdown("Empty", "No reqs", [])
    assert "# Empty" in md
    assert "## Purpose" in md
    assert "## Requirements" not in md


def test_serializer_handles_no_purpose():
    md = spec_parser.spec_to_markdown("No Purpose", "", [{"name": "R", "description": "D", "scenarios": []}])
    assert "# No Purpose" in md
    assert "## Purpose" not in md
    assert "### Requirement: R" in md


# ---------------------------------------------------------------------------
# openspec_spec_create
# ---------------------------------------------------------------------------

def _make_project(tmp_path: Path) -> Path:
    """Create a minimal openspec project structure."""
    root = tmp_path / "project"
    (root / "openspec" / "specs").mkdir(parents=True)
    (root / "openspec" / "changes").mkdir(parents=True)
    return root


def _sample_requirements():
    return [
        {
            "name": "Create spec",
            "description": "The system SHALL create a spec.",
            "scenarios": [
                {
                    "name": "Happy path",
                    "steps": [
                        {"type": "GIVEN", "text": "a project"},
                        {"type": "WHEN", "text": "an agent creates a spec"},
                        {"type": "THEN", "text": "the spec is written"},
                    ],
                },
            ],
        },
    ]


def test_spec_create_writes_baseline_spec(tmp_path):
    root = _make_project(tmp_path)
    result = json.loads(tools.openspec_spec_create({
        "workdir": str(root),
        "spec": "my-spec",
        "title": "My Spec",
        "purpose": "Test purpose",
        "requirements": _sample_requirements(),
    }))
    assert result["ok"] is True
    assert result["spec"] == "my-spec"
    assert result["change"] is None
    assert result["path"] == "openspec/specs/my-spec/spec.md"
    spec_file = root / "openspec" / "specs" / "my-spec" / "spec.md"
    assert spec_file.is_file()
    content = spec_file.read_text()
    assert "# My Spec" in content
    assert "### Requirement: Create spec" in content


def test_spec_create_writes_change_scoped_spec(tmp_path):
    root = _make_project(tmp_path)
    change_dir = root / "openspec" / "changes" / "my-change"
    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text("## Why\nTest")

    result = json.loads(tools.openspec_spec_create({
        "workdir": str(root),
        "spec": "feature-spec",
        "change": "my-change",
        "title": "Feature Spec",
        "purpose": "Feature purpose",
        "requirements": _sample_requirements(),
    }))
    assert result["ok"] is True
    assert result["change"] == "my-change"
    assert result["path"] == "openspec/changes/my-change/specs/feature-spec/spec.md"
    spec_file = change_dir / "specs" / "feature-spec" / "spec.md"
    assert spec_file.is_file()


def test_spec_create_refuses_overwrite(tmp_path):
    root = _make_project(tmp_path)
    # First create succeeds
    r1 = json.loads(tools.openspec_spec_create({
        "workdir": str(root),
        "spec": "existing",
        "title": "First",
        "purpose": "P",
        "requirements": _sample_requirements(),
    }))
    assert r1["ok"] is True

    # Second create refuses without force
    r2 = json.loads(tools.openspec_spec_create({
        "workdir": str(root),
        "spec": "existing",
        "title": "Second",
        "purpose": "P2",
        "requirements": _sample_requirements(),
    }))
    assert r2["ok"] is False
    assert "already exists" in r2["error"]
    # Original content preserved
    content = (root / "openspec" / "specs" / "existing" / "spec.md").read_text()
    assert "# First" in content


def test_spec_create_force_overwrites(tmp_path):
    root = _make_project(tmp_path)
    tools.openspec_spec_create({
        "workdir": str(root),
        "spec": "overwritable",
        "title": "Original",
        "purpose": "P",
        "requirements": _sample_requirements(),
    })
    r2 = json.loads(tools.openspec_spec_create({
        "workdir": str(root),
        "spec": "overwritable",
        "title": "Replaced",
        "purpose": "P2",
        "requirements": _sample_requirements(),
        "force": True,
    }))
    assert r2["ok"] is True
    content = (root / "openspec" / "specs" / "overwritable" / "spec.md").read_text()
    assert "# Replaced" in content


def test_spec_create_invalid_slug(tmp_path):
    root = _make_project(tmp_path)
    for bad in ["../escape", "UPPER CASE", "has_underscore", "with/slash"]:
        r = json.loads(tools.openspec_spec_create({
            "workdir": str(root),
            "spec": bad,
            "title": "T",
            "purpose": "P",
            "requirements": _sample_requirements(),
        }))
        assert r["ok"] is False, f"expected failure for slug: {bad}"
        assert "kebab-case" in r["error"] or "parent references" in r["error"]


def test_spec_create_missing_title(tmp_path):
    root = _make_project(tmp_path)
    r = json.loads(tools.openspec_spec_create({
        "workdir": str(root),
        "spec": "test",
        "purpose": "P",
        "requirements": _sample_requirements(),
    }))
    assert r["ok"] is False
    assert "title" in r["error"]


def test_spec_create_missing_purpose(tmp_path):
    root = _make_project(tmp_path)
    r = json.loads(tools.openspec_spec_create({
        "workdir": str(root),
        "spec": "test",
        "title": "T",
        "requirements": _sample_requirements(),
    }))
    assert r["ok"] is False
    assert "purpose" in r["error"]


def test_spec_create_empty_requirements(tmp_path):
    root = _make_project(tmp_path)
    r = json.loads(tools.openspec_spec_create({
        "workdir": str(root),
        "spec": "test",
        "title": "T",
        "purpose": "P",
        "requirements": [],
    }))
    assert r["ok"] is False
    assert "requirements" in r["error"]


# ---------------------------------------------------------------------------
# openspec_spec_show
# ---------------------------------------------------------------------------

def test_spec_show_returns_structured_json(tmp_path):
    root = _make_project(tmp_path)
    # Create a spec first
    tools.openspec_spec_create({
        "workdir": str(root),
        "spec": "showable",
        "title": "Showable Spec",
        "purpose": "Show purpose",
        "requirements": _sample_requirements(),
    })

    result = json.loads(tools.openspec_spec_show({
        "workdir": str(root),
        "spec": "showable",
    }))
    assert result["ok"] is True
    assert result["title"] == "Showable Spec"
    assert result["purpose"] == "Show purpose"
    assert len(result["requirements"]) == 1
    req = result["requirements"][0]
    assert req["name"] == "Create spec"
    assert len(req["scenarios"]) == 1
    assert req["scenarios"][0]["name"] == "Happy path"
    assert len(req["scenarios"][0]["steps"]) == 3


def test_spec_show_change_scoped(tmp_path):
    root = _make_project(tmp_path)
    change_dir = root / "openspec" / "changes" / "feat"
    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text("## Why\nTest")

    tools.openspec_spec_create({
        "workdir": str(root),
        "spec": "delta-spec",
        "change": "feat",
        "title": "Delta",
        "purpose": "Delta purpose",
        "requirements": _sample_requirements(),
    })

    result = json.loads(tools.openspec_spec_show({
        "workdir": str(root),
        "spec": "delta-spec",
        "change": "feat",
    }))
    assert result["ok"] is True
    assert result["change"] == "feat"
    assert result["title"] == "Delta"


def test_spec_show_missing_spec(tmp_path):
    root = _make_project(tmp_path)
    result = json.loads(tools.openspec_spec_show({
        "workdir": str(root),
        "spec": "nonexistent",
    }))
    assert result["ok"] is False
    assert "not found" in result["error"]


def test_spec_show_round_trip_with_real_spec(tmp_path):
    """Create a spec with structured input, then show it — the round-trip must match."""
    root = _make_project(tmp_path)
    original_reqs = [
        {
            "name": "Round Trip Req",
            "description": "Description text.",
            "scenarios": [
                {
                    "name": "Scenario One",
                    "steps": [
                        {"type": "GIVEN", "text": "a context"},
                        {"type": "WHEN", "text": "an action"},
                        {"type": "THEN", "text": "a result"},
                    ],
                },
            ],
        },
    ]
    tools.openspec_spec_create({
        "workdir": str(root),
        "spec": "round-trip",
        "title": "Round Trip Spec",
        "purpose": "Round trip purpose",
        "requirements": original_reqs,
    })

    shown = json.loads(tools.openspec_spec_show({
        "workdir": str(root),
        "spec": "round-trip",
    }))
    assert shown["ok"] is True
    assert shown["title"] == "Round Trip Spec"
    assert shown["purpose"] == "Round trip purpose"
    req = shown["requirements"][0]
    assert req["name"] == "Round Trip Req"
    assert req["description"] == "Description text."
    scn = req["scenarios"][0]
    assert scn["name"] == "Scenario One"
    assert [s["type"] for s in scn["steps"]] == ["GIVEN", "WHEN", "THEN"]
    assert [s["text"] for s in scn["steps"]] == ["a context", "an action", "a result"]


# ---------------------------------------------------------------------------
# openspec_spec_list
# ---------------------------------------------------------------------------

def test_spec_list_baseline(tmp_path):
    root = _make_project(tmp_path)
    # Create two baseline specs
    for name in ["alpha-spec", "beta-spec"]:
        tools.openspec_spec_create({
            "workdir": str(root),
            "spec": name,
            "title": name.title(),
            "purpose": "P",
            "requirements": _sample_requirements(),
        })

    result = json.loads(tools.openspec_spec_list({
        "workdir": str(root),
    }))
    assert result["ok"] is True
    assert result["change"] is None
    assert result["count"] == 2
    assert "alpha-spec" in result["specs"]
    assert "beta-spec" in result["specs"]


def test_spec_list_change_scoped(tmp_path):
    root = _make_project(tmp_path)
    change_dir = root / "openspec" / "changes" / "my-change"
    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text("## Why\nTest")

    for name in ["delta-a", "delta-b"]:
        tools.openspec_spec_create({
            "workdir": str(root),
            "spec": name,
            "change": "my-change",
            "title": name.title(),
            "purpose": "P",
            "requirements": _sample_requirements(),
        })

    result = json.loads(tools.openspec_spec_list({
        "workdir": str(root),
        "change": "my-change",
    }))
    assert result["ok"] is True
    assert result["change"] == "my-change"
    assert result["count"] == 2
    assert "delta-a" in result["specs"]
    assert "delta-b" in result["specs"]


def test_spec_list_empty(tmp_path):
    root = _make_project(tmp_path)
    result = json.loads(tools.openspec_spec_list({
        "workdir": str(root),
    }))
    assert result["ok"] is True
    assert result["count"] == 0
    assert result["specs"] == []


def test_spec_list_missing_specs_dir(tmp_path):
    """Listing should return empty when the specs directory doesn't exist."""
    root = tmp_path / "bare-project"
    (root / "openspec").mkdir(parents=True)

    result = json.loads(tools.openspec_spec_list({
        "workdir": str(root),
    }))
    assert result["ok"] is True
    assert result["count"] == 0


# ---------------------------------------------------------------------------
# Integration: create → show → list
# ---------------------------------------------------------------------------

def test_full_workflow_create_show_list(tmp_path):
    """End-to-end: create a spec, show it, list it."""
    root = _make_project(tmp_path)

    # Create
    created = json.loads(tools.openspec_spec_create({
        "workdir": str(root),
        "spec": "workflow-spec",
        "title": "Workflow Spec",
        "purpose": "Workflow purpose",
        "requirements": _sample_requirements(),
    }))
    assert created["ok"] is True

    # Show
    shown = json.loads(tools.openspec_spec_show({
        "workdir": str(root),
        "spec": "workflow-spec",
    }))
    assert shown["ok"] is True
    assert shown["title"] == "Workflow Spec"

    # List
    listed = json.loads(tools.openspec_spec_list({
        "workdir": str(root),
    }))
    assert listed["ok"] is True
    assert "workflow-spec" in listed["specs"]

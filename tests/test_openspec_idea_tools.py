import json
import subprocess
from pathlib import Path

import pytest
import tools


def parse(payload):
    return json.loads(payload)


def test_uniform_lifecycle_tool_names_are_exposed_and_old_idea_names_removed():
    for name in (
        "openspec_idea_create",
        "openspec_idea_enrich",
        "openspec_idea_promote",
        "openspec_task_list",
        "openspec_task_set_status",
        "openspec_change_create",
        "openspec_change_promote",
        "openspec_change_archive",
        "openspec_change_unarchive",
    ):
        assert hasattr(tools, name)

    for old_name in (
        "openspec_create_idea",
        "openspec_enrich_idea",
        "openspec_promote_idea",
    ):
        assert not hasattr(tools, old_name)


def test_idea_create_writes_markdown_with_safe_slug_and_collision_suffix(tmp_path):
    first = parse(tools.openspec_idea_create({
        "workdir": str(tmp_path),
        "title": "Agent + Human Feedback Loop!",
        "prompt": "Capture raw user and agent ideas in one lane.",
        "origin": "human",
        "tags": ["orchestration", "feedback"],
        "notes": "Start small.",
    }))
    second = parse(tools.openspec_idea_create({
        "workdir": str(tmp_path),
        "title": "Agent + Human Feedback Loop!",
        "prompt": "A second prompt should not overwrite the first.",
    }))

    assert first["ok"] is True
    assert first["slug"] == "agent-human-feedback-loop"
    assert second["ok"] is True
    assert second["slug"] == "agent-human-feedback-loop-2"

    first_path = Path(first["path"])
    second_path = Path(second["path"])
    assert first_path.is_file()
    assert second_path.is_file()
    assert first_path.read_text(encoding="utf-8").startswith("# Agent + Human Feedback Loop!")
    assert "Origin: human" in first_path.read_text(encoding="utf-8")
    assert "Tags: orchestration, feedback" in first_path.read_text(encoding="utf-8")
    assert "Capture raw user and agent ideas" in first_path.read_text(encoding="utf-8")
    assert "A second prompt" in second_path.read_text(encoding="utf-8")


def test_idea_create_refuses_empty_title_or_prompt_without_writing(tmp_path):
    result = parse(tools.openspec_idea_create({
        "workdir": str(tmp_path),
        "title": " ",
        "prompt": "Something",
    }))

    assert result["ok"] is False
    assert "title is required" in result["error"]
    assert not (tmp_path / "openspec" / "ideas").exists()


def test_idea_enrich_inserts_and_replaces_structured_report(tmp_path):
    created = parse(tools.openspec_idea_create({
        "workdir": str(tmp_path),
        "title": "Idea enrichment",
        "prompt": "Assess ideas consistently.",
    }))

    enriched = parse(tools.openspec_idea_enrich({
        "workdir": str(tmp_path),
        "idea": created["slug"],
        "problem": "Ideas lack consistent evaluation.",
        "proposed_direction": "Use a rubric-backed report.",
        "key_questions": ["Who reviews it?", "When promote?"],
        "feasibility": "High",
        "tshirt_size": "M",
        "size_justification": "Three small tools plus tests.",
        "risks": ["Over-automation"],
        "suggested_next_step": "Promote after review",
    }))
    updated = parse(tools.openspec_idea_enrich({
        "workdir": str(tmp_path),
        "idea": created["slug"],
        "problem": "Updated problem.",
        "feasibility": "Medium",
        "tshirt_size": "S",
        "size_justification": "Reduced scope.",
        "suggested_next_step": "Keep as idea",
    }))

    assert enriched["ok"] is True
    assert updated["ok"] is True
    content = Path(created["path"]).read_text(encoding="utf-8")
    assert content.count("## Enrichment Report") == 1
    assert "Updated problem." in content
    assert "Ideas lack consistent evaluation." not in content
    assert "Feasibility: Medium" in content
    assert "T-Shirt Size: S" in content


def test_idea_promote_creates_change_scaffold_with_traceability_and_refuses_collision(tmp_path):
    created = parse(tools.openspec_idea_create({
        "workdir": str(tmp_path),
        "title": "Promote me",
        "prompt": "Turn a reviewed idea into a change.",
    }))

    promoted = parse(tools.openspec_idea_promote({
        "workdir": str(tmp_path),
        "idea": created["slug"],
        "change": "promote-reviewed-idea",
        "summary": "Add promotion workflow.",
    }))
    collision = parse(tools.openspec_idea_promote({
        "workdir": str(tmp_path),
        "idea": created["slug"],
        "change": "promote-reviewed-idea",
    }))

    assert promoted["ok"] is True
    change_dir = Path(promoted["change_path"])
    assert (change_dir / "proposal.md").is_file()
    assert (change_dir / "tasks.md").is_file()
    assert (change_dir / "specs" / "promote-reviewed-idea" / "spec.md").is_file()
    assert "## ADDED Requirements" in (change_dir / "specs" / "promote-reviewed-idea" / "spec.md").read_text(encoding="utf-8")
    assert "Source Idea" in (change_dir / "proposal.md").read_text(encoding="utf-8")
    assert created["relative_path"] in (change_dir / "proposal.md").read_text(encoding="utf-8")
    assert "Turn a reviewed idea into a change." in (change_dir / "proposal.md").read_text(encoding="utf-8")
    assert collision["ok"] is False
    assert "already exists" in collision["error"]


def test_change_create_and_promote_support_draft_to_todo_flow(tmp_path):
    created = parse(tools.openspec_change_create({
        "workdir": str(tmp_path),
        "change": "direct-change",
        "title": "Direct Change",
        "summary": "Create a change without an idea first.",
    }))
    assert created["ok"] is True
    change_dir = Path(created["change_path"])
    assert (change_dir / "proposal.md").is_file()
    assert not (change_dir / "tasks.md").exists()

    promoted = parse(tools.openspec_change_promote({
        "workdir": str(tmp_path),
        "change": "direct-change",
        "tasks": ["Refine scope", "Implement behavior"],
    }))

    assert promoted["ok"] is True
    assert promoted["status"] == "todo"
    assert (change_dir / "tasks.md").is_file()
    assert (change_dir / "specs" / "direct-change" / "spec.md").is_file()
    assert "- [ ] 1.1 Refine scope" in (change_dir / "tasks.md").read_text(encoding="utf-8")


def test_task_list_and_set_status_update_requested_checklist_items(tmp_path):
    parse(tools.openspec_change_create({
        "workdir": str(tmp_path),
        "change": "task-change",
        "title": "Task Change",
        "summary": "Test task lifecycle.",
        "tasks": ["First task", "Second task"],
        "with_spec": True,
    }))

    listed = parse(tools.openspec_task_list({"workdir": str(tmp_path), "change": "task-change"}))
    assert listed["ok"] is True
    assert [task["id"] for task in listed["tasks"]] == ["1.1", "1.2"]
    assert listed["counts"] == {"total": 2, "done": 0, "todo": 2}
    assert listed["status"] == "todo"

    updated = parse(tools.openspec_task_set_status({
        "workdir": str(tmp_path),
        "change": "task-change",
        "tasks": ["1.1"],
        "status": "done",
    }))
    assert updated["ok"] is True
    assert updated["counts"] == {"total": 2, "done": 1, "todo": 1}
    assert updated["status"] == "in_progress"

    done = parse(tools.openspec_task_set_status({
        "workdir": str(tmp_path),
        "change": "task-change",
        "tasks": ["1.2"],
        "status": "done",
    }))
    assert done["counts"] == {"total": 2, "done": 2, "todo": 0}
    assert done["status"] == "done"


def test_change_archive_refuses_incomplete_tasks_then_unarchive_restores_active_change(tmp_path):
    parse(tools.openspec_change_create({
        "workdir": str(tmp_path),
        "change": "archive-me",
        "title": "Archive Me",
        "summary": "Archive lifecycle.",
        "tasks": ["Finish this"],
        "with_spec": True,
    }))

    refused = parse(tools.openspec_change_archive({"workdir": str(tmp_path), "change": "archive-me"}))
    assert refused["ok"] is False
    assert "not complete" in refused["error"]

    parse(tools.openspec_task_set_status({
        "workdir": str(tmp_path),
        "change": "archive-me",
        "tasks": ["1.1"],
        "status": "done",
    }))
    archived = parse(tools.openspec_change_archive({"workdir": str(tmp_path), "change": "archive-me"}))
    assert archived["ok"] is True
    assert not (tmp_path / "openspec" / "changes" / "archive-me").exists()
    assert (tmp_path / "openspec" / "changes" / "archive" / "archive-me").is_dir()

    unarchived = parse(tools.openspec_change_unarchive({"workdir": str(tmp_path), "change": "archive-me"}))
    assert unarchived["ok"] is True
    assert (tmp_path / "openspec" / "changes" / "archive-me").is_dir()
    assert not (tmp_path / "openspec" / "changes" / "archive" / "archive-me").exists()


def test_generated_scaffolds_validate_with_openspec_cli(tmp_path):
    exe = tools._openspec_bin()
    if not exe:
        pytest.skip("openspec CLI is not available")

    created = parse(tools.openspec_idea_create({
        "workdir": str(tmp_path),
        "title": "Valid promoted scaffold",
        "prompt": "Generated changes should validate before refinement.",
    }))
    idea_promoted = parse(tools.openspec_idea_promote({
        "workdir": str(tmp_path),
        "idea": created["slug"],
        "change": "valid-promoted-scaffold",
    }))
    change_created = parse(tools.openspec_change_create({
        "workdir": str(tmp_path),
        "change": "valid-created-scaffold",
        "title": "Valid Created Scaffold",
        "summary": "Generated direct changes should validate.",
        "tasks": ["Do the thing"],
        "with_spec": True,
    }))

    for change in (idea_promoted["change"], change_created["change"]):
        proc = subprocess.run(
            [exe, "validate", change, "--strict", "--json", "--no-interactive"],
            cwd=str(tmp_path),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["summary"]["totals"]["failed"] == 0

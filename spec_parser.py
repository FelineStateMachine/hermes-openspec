"""Shared OpenSpec spec parser and semantic diff.

Importable by both ``tools.py`` (agent tool handlers) and
``dashboard/plugin_api.py`` (dashboard backend) so the spec parsing
and diffing logic lives in one place.

The parser mirrors the frontend ``parseSpec`` function in
``dashboard/dist/index.js`` — same state machine, same output structure.
"""

from __future__ import annotations

import difflib
from typing import Any


def parse_spec(md: str | None) -> dict[str, Any]:
    """Parse OpenSpec spec markdown into structured data.

    Returns ``{ title, purpose, requirements: [...] }`` where each
    requirement is ``{ name, description, scenarios: [...] }`` and each
    scenario is ``{ name, steps: [{ type, text }] }``.
    """
    if not md:
        return {"title": "", "purpose": "", "requirements": []}

    lines = md.split("\n")
    title = ""
    purpose = ""
    reqs: list[dict[str, Any]] = []
    state = "top"  # top | purpose | reqDesc | scenario
    current_req: dict[str, Any] | None = None
    current_scn: dict[str, Any] | None = None

    for line in lines:
        trim = line.strip()

        # Title: "# Title" but not "## Title"
        if trim.startswith("# ") and not trim.startswith("## "):
            title = trim[2:].strip().removesuffix("Specification").strip()
            state = "top"
            continue

        if trim.lower().startswith("## purpose"):
            state = "purpose"
            continue

        if trim.lower().startswith("## requirements"):
            state = "top"
            continue

        m_req = re_match(r"^###\s+Requirement:\s*(.+)$", trim)
        if m_req:
            current_req = {"name": m_req.group(1).strip(), "description": "", "scenarios": []}
            reqs.append(current_req)
            current_scn = None
            state = "reqDesc"
            continue

        m_scn = re_match(r"^####\s+Scenario:\s*(.+)$", trim)
        if m_scn:
            current_scn = {"name": m_scn.group(1).strip(), "steps": []}
            if current_req is not None:
                current_req["scenarios"].append(current_scn)
            state = "scenario"
            continue

        # Accumulate text based on state
        if not trim:
            continue

        if state == "purpose":
            purpose = f"{purpose}\n{trim}" if purpose else trim
        elif state == "reqDesc":
            if current_req is not None:
                current_req["description"] = (
                    f"{current_req['description']}\n{trim}"
                    if current_req["description"]
                    else trim
                )
        elif state == "scenario":
            if current_scn is not None:
                step = re_match(r"^[-*]\s+\*\*(\w+)\*\*\s*(.+)$", trim)
                if step:
                    current_scn["steps"].append({
                        "type": step.group(1).upper(),
                        "text": step.group(2).strip(),
                    })
                elif current_scn["steps"]:
                    # Non-bullet text inside scenario — append to last step
                    current_scn["steps"][-1]["text"] += f" {trim}"

    return {"title": title, "purpose": purpose, "requirements": reqs}


def _scenario_key(scn: dict[str, Any]) -> str:
    """Normalize a scenario for comparison by name."""
    return scn["name"]


def _requirement_key(req: dict[str, Any]) -> str:
    """Normalize a requirement for comparison by name."""
    return req["name"]


def _scenarios_equal(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    if a is None or b is None:
        return a is b
    return a["name"] == b["name"] and a["steps"] == b["steps"]


def _requirements_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (
        a["name"] == b["name"]
        and a["description"] == b["description"]
        and a["scenarios"] == b["scenarios"]
    )


def semantic_spec_diff(before_md: str | None, after_md: str | None) -> dict[str, Any]:
    """Compare two spec markdown strings at the requirement/scenario level.

    Returns a structured delta::

        {
            "status": "added" | "modified" | "deleted" | "unchanged",
            "requirements": {
                "added": [...],
                "modified": [{ name, before, after, scenarios_added, ... }],
                "removed": [...],
                "unchanged": ["name", ...],
            },
        }
    """
    before = parse_spec(before_md)
    after = parse_spec(after_md)

    before_reqs = {r["name"]: r for r in before["requirements"]}
    after_reqs = {r["name"]: r for r in after["requirements"]}

    added: list[dict[str, Any]] = []
    modified: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    unchanged: list[str] = []

    all_names = set(before_reqs) | set(after_reqs)
    for name in sorted(all_names):
        b_req = before_reqs.get(name)
        a_req = after_reqs.get(name)

        if b_req is None and a_req is not None:
            added.append(a_req)
        elif b_req is not None and a_req is None:
            removed.append(b_req)
        elif b_req is not None and a_req is not None:
            if _requirements_equal(b_req, a_req):
                unchanged.append(name)
            else:
                # Diff scenarios within the modified requirement
                b_scns = {s["name"]: s for s in b_req["scenarios"]}
                a_scns = {s["name"]: s for s in a_req["scenarios"]}

                scn_added: list[dict[str, Any]] = []
                scn_modified: list[dict[str, Any]] = []
                scn_removed: list[dict[str, Any]] = []

                for scn_name in sorted(set(b_scns) | set(a_scns)):
                    b_scn = b_scns.get(scn_name)
                    a_scn = a_scns.get(scn_name)
                    if b_scn is None and a_scn is not None:
                        scn_added.append(a_scn)
                    elif b_scn is not None and a_scn is None:
                        scn_removed.append(b_scn)
                    elif b_scn is not None and a_scn is not None:
                        if not _scenarios_equal(b_scn, a_scn):
                            scn_modified.append({
                                "name": scn_name,
                                "before": b_scn,
                                "after": a_scn,
                            })

                modified.append({
                    "name": name,
                    "before": {
                        "description": b_req["description"],
                        "scenarios": b_req["scenarios"],
                    },
                    "after": {
                        "description": a_req["description"],
                        "scenarios": a_req["scenarios"],
                    },
                    "scenarios_added": scn_added,
                    "scenarios_modified": scn_modified,
                    "scenarios_removed": scn_removed,
                })

    # Overall status
    if not before_md and not after_md:
        status = "unchanged"
    elif not before_md:
        status = "added"
    elif not after_md:
        status = "deleted"
    elif not added and not modified and not removed:
        status = "unchanged"
    else:
        status = "modified"

    return {
        "status": status,
        "requirements": {
            "added": added,
            "modified": modified,
            "removed": removed,
            "unchanged": unchanged,
        },
    }


def semantic_summary(diff: dict[str, Any]) -> dict[str, int]:
    """Extract compact counts from a semantic diff for list display."""
    reqs = diff.get("requirements", {})
    return {
        "added": len(reqs.get("added", [])),
        "modified": len(reqs.get("modified", [])),
        "removed": len(reqs.get("removed", [])),
    }


def unified_diff(before_md: str | None, after_md: str | None, path: str = "spec") -> str:
    """Return a unified line diff for fallback display."""
    return "\n".join(
        difflib.unified_diff(
            (before_md or "").splitlines(),
            (after_md or "").splitlines(),
            fromfile=f"before/{path}",
            tofile=f"after/{path}",
            lineterm="",
        )
    )


def spec_to_markdown(title: str, purpose: str, requirements: list[dict[str, Any]]) -> str:
    """Serialize structured spec data into OpenSpec spec markdown.

    Inverse of ``parse_spec`` — takes ``{title, purpose, requirements}`` and
    produces ``# Title`` / ``## Purpose`` / ``## Requirements`` /
    ``### Requirement:`` / ``#### Scenario:`` formatted markdown.

    Each requirement is ``{name, description, scenarios}`` and each
    scenario is ``{name, steps: [{type, text}]}``.
    """
    lines: list[str] = [f"# {title}", ""]

    if purpose:
        lines.append("## Purpose")
        lines.append("")
        lines.append(purpose)
        lines.append("")

    if requirements:
        lines.append("## Requirements")
        lines.append("")
        for req in requirements:
            name = str(req.get("name") or "").strip()
            desc = str(req.get("description") or "").strip()
            lines.append(f"### Requirement: {name}")
            if desc:
                lines.append(desc)
            lines.append("")
            for scn in req.get("scenarios") or []:
                scn_name = str(scn.get("name") or "").strip()
                lines.append(f"#### Scenario: {scn_name}")
                lines.append("")
                for step in scn.get("steps") or []:
                    step_type = str(step.get("type") or "THEN").strip().upper()
                    step_text = str(step.get("text") or "").strip()
                    lines.append(f"- **{step_type}** {step_text}")
                lines.append("")

    # Trim trailing blank lines, ensure single trailing newline
    return "\n".join(lines).rstrip() + "\n"


def re_match(pattern: str, string: str):
    """Wrapper to avoid importing re at module level in callers."""
    import re
    return re.match(pattern, string, re.IGNORECASE)

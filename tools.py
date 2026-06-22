"""OpenSpec Hermes tool handlers."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_OUTPUT_CHARS = 50_000

_ARTIFACT_ALIASES = {"spec": "specs"}


def _openspec_bin() -> str | None:
    configured = os.getenv("OPENSPEC_BIN", "").strip()
    candidates = [
        configured,
        shutil.which("openspec") or "",
        str(Path.home() / ".npm-global" / "bin" / "openspec"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _resolve_workdir(value: Any) -> tuple[Path | None, str | None]:
    raw = str(value or "").strip()
    if not raw:
        return Path.cwd(), None
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    if not p.exists() or not p.is_dir():
        return None, f"workdir does not exist or is not a directory: {p}"
    return p, None


def _json_or_text(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        return ""
    try:
        return json.loads(stripped)
    except Exception:
        return stripped


def _normalize_artifact(value: str) -> str:
    artifact = (value or "").strip()
    return _ARTIFACT_ALIASES.get(artifact, artifact)


def _run(args: list[str], workdir: Any = None) -> str:
    exe = _openspec_bin()
    if not exe:
        return json.dumps({
            "ok": False,
            "error": "openspec executable not found. Install OpenSpec or set OPENSPEC_BIN.",
        })

    cwd, err = _resolve_workdir(workdir)
    if err:
        return json.dumps({"ok": False, "error": err})

    env = os.environ.copy()
    env.setdefault("OPENSPEC_TELEMETRY", "0")
    env.setdefault("NO_COLOR", "1")

    cmd = [exe, *args]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return json.dumps({
            "ok": False,
            "command": cmd,
            "workdir": str(cwd),
            "error": "openspec command timed out after 120s",
        })
    except Exception as exc:
        return json.dumps({
            "ok": False,
            "command": cmd,
            "workdir": str(cwd),
            "error": str(exc),
        })

    stdout = proc.stdout[-MAX_OUTPUT_CHARS:]
    stderr = proc.stderr[-MAX_OUTPUT_CHARS:]
    return json.dumps({
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "command": cmd,
        "workdir": str(cwd),
        "stdout": _json_or_text(stdout),
        "stderr": _json_or_text(stderr),
        "truncated": len(proc.stdout) > MAX_OUTPUT_CHARS or len(proc.stderr) > MAX_OUTPUT_CHARS,
    })


def _template_instruction_fallback(artifact: str, reason: str, workdir: Any = None, schema: str = "") -> str | None:
    """Return template-backed instructions when OpenSpec needs a change first."""
    if "No changes found" not in reason:
        return None
    artifact = _normalize_artifact(artifact)
    if not artifact:
        return None

    templates_args = ["templates", "--json"]
    if schema:
        templates_args.extend(["--schema", schema])
    templates_result = json.loads(_run(templates_args, workdir))
    if not templates_result.get("ok") or not isinstance(templates_result.get("stdout"), dict):
        return None

    entry = templates_result["stdout"].get(artifact)
    if not isinstance(entry, dict):
        return None
    path = Path(str(entry.get("path") or "")).expanduser()
    if not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    fallback = dict(templates_result)
    fallback["ok"] = True
    fallback["stdout"] = {
        "artifact": artifact,
        "fallback": "template",
        "reason": reason,
        "templatePath": str(path),
        "source": entry.get("source"),
        "content": content,
    }
    fallback["stderr"] = ""
    return json.dumps(fallback)


def _registry_module():
    """Import the plugin-local OpenSpec registry (``plugins.openspec.registry``).

    Tolerates odd sys.path setups where the package isn't importable by name;
    in that case fall back to a path-based load from this file's location.
    """
    try:
        from . import registry  # type: ignore
        return registry
    except Exception:
        pass
    try:
        import importlib.util
        candidate = Path(__file__).resolve().parent / "registry.py"
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("openspec_registry", candidate)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
    except Exception:
        pass
    return None


def _read_doc(path: Path) -> str:
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return ""


def _iter_change_dirs(root: Path):
    """Yield ``(change_dir, archived)`` for every change folder with a proposal."""
    changes_root = root / "openspec" / "changes"
    if changes_root.is_dir():
        for child in sorted(changes_root.iterdir()):
            if child.name == "archive":
                continue
            if child.is_dir() and (child / "proposal.md").is_file():
                yield child, False
        archive_root = changes_root / "archive"
        if archive_root.is_dir():
            for child in sorted(archive_root.iterdir()):
                if child.is_dir() and (child / "proposal.md").is_file():
                    yield child, True


def _resolve_change(root: Path, registry, change_ref: str) -> tuple[Path | None, bool]:
    """Map a change token (``os_xxx``) — or a literal change name (legacy) — to a
    change folder under ``root``. Returns ``(change_dir, archived)``."""
    for change_dir, archived in _iter_change_dirs(root):
        if registry.change_token(change_dir.name) == change_ref or change_dir.name == change_ref:
            return change_dir, archived
    return None, False


def _iter_specs(root: Path):
    specs_root = root / "openspec" / "specs"
    if specs_root.is_dir():
        for child in sorted(specs_root.rglob("*.md")):
            if child.is_file():
                yield child.relative_to(specs_root).as_posix(), child


def _resolve_spec(root: Path, registry, spec_ref: str) -> tuple[str | None, Path | None]:
    for rel, path in _iter_specs(root):
        if registry.change_token(f"spec:{rel}") == spec_ref or rel == spec_ref:
            return rel, path
    return None, None


def openspec_context(args: dict, **kwargs) -> str:
    """Resolve a copyable identifier (``puzzletea`` or ``puzzletea/os_xxx``) into
    repo path + (optionally) the change's proposal/tasks/design/specs content."""
    registry = _registry_module()
    if registry is None:
        return json.dumps({
            "ok": False,
            "error": "OpenSpec registry unavailable (plugins.openspec.registry not importable).",
        })

    identifier = str(args.get("identifier") or "").strip()
    if not identifier:
        return json.dumps({"ok": False, "error": "identifier is required (e.g. 'puzzletea' or 'puzzletea/os_a1b2c3')"})

    source_ref, change_ref = registry.parse_identifier(identifier)
    # Resolve source by vanity name first, then fall back to a legacy source token.
    source = registry.get_source_by_name(source_ref) or registry.get_source(source_ref)
    if source is None:
        return json.dumps({"ok": False, "error": f"No registered OpenSpec source for '{source_ref}'."})

    name = registry.effective_name(source)
    repo_path = Path(source["path"]).expanduser()
    if not (repo_path / "openspec").is_dir():
        return json.dumps({
            "ok": False,
            "name": name,
            "path": str(repo_path),
            "error": f"openspec/ directory not found at {repo_path} (repo may have moved).",
        })

    result: dict[str, Any] = {
        "ok": True,
        "name": name,
        "path": str(repo_path),
        "workdir": str(repo_path),
        "hint": "Use this path as 'workdir' for other openspec_* tools, or run openspec commands from here.",
    }

    if change_ref:
        change_dir, archived = _resolve_change(repo_path, registry, change_ref)
        if change_dir is None:
            spec_rel, spec_path = _resolve_spec(repo_path, registry, change_ref)
            if spec_rel and spec_path:
                result["spec"] = {
                    "path": spec_rel,
                    "token": registry.change_token(f"spec:{spec_rel}"),
                    "content": _read_doc(spec_path),
                }
                return json.dumps(result)
            return json.dumps({
                "ok": False,
                "name": name,
                "path": str(repo_path),
                "error": f"No change or spec matching '{change_ref}' under openspec/.",
            })
        specs_root = change_dir / "specs"
        specs = []
        if specs_root.is_dir():
            for child in sorted(specs_root.rglob("*.md")):
                specs.append({
                    "path": child.relative_to(specs_root).as_posix(),
                    "content": _read_doc(child),
                })
        result["change"] = {
            "name": change_dir.name,
            "token": registry.change_token(change_dir.name),
            "archived": archived,
            "proposal": _read_doc(change_dir / "proposal.md"),
            "tasks": _read_doc(change_dir / "tasks.md"),
            "design": _read_doc(change_dir / "design.md"),
            "specs": specs,
        }
    else:
        changes = [
            {"name": change_dir.name, "token": registry.change_token(change_dir.name)}
            for change_dir, archived in _iter_change_dirs(repo_path)
            if not archived
        ]
        specs = [
            {"path": rel, "token": registry.change_token(f"spec:{rel}")}
            for rel, _path in _iter_specs(repo_path)
        ]
        result["changes"] = changes
        result["specs"] = specs
        result["hint"] = (
            "Active changes are listed in 'changes'; current specs are listed in 'specs'. Re-call with identifier "
            f"'{name}/<token>' to load a specific change or spec, or use workdir with other openspec_* tools."
        )

    return json.dumps(result)


_SLUG_RE = re.compile(r"[^a-z0-9]+")
_VALID_CHANGE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
_ENRICHMENT_START = "<!-- OPENSPEC_IDEA_ENRICHMENT_START -->"
_ENRICHMENT_END = "<!-- OPENSPEC_IDEA_ENRICHMENT_END -->"
_VALID_FEASIBILITY = {"low", "medium", "high"}
_VALID_TSHIRT = {"xs", "s", "m", "l", "xl"}


def _error(message: str, **extra: Any) -> str:
    payload = {"ok": False, "error": message}
    payload.update(extra)
    return json.dumps(payload)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slugify(value: str, fallback: str = "idea") -> str:
    slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return slug or fallback


def _resolve_project(args: dict) -> tuple[Path | None, str | None, dict[str, Any]]:
    """Resolve a tool call to a project root.

    Prefer explicit workdir. Also accept a registered OpenSpec identifier/source
    name so agents can call write tools with the same project handles used by
    ``openspec_context``.
    """
    workdir = args.get("workdir")
    if workdir:
        root, err = _resolve_workdir(workdir)
        return root, err, {}

    identifier = str(args.get("identifier") or args.get("project") or "").strip()
    if identifier:
        registry = _registry_module()
        if registry is None:
            return None, "OpenSpec registry unavailable (plugins.openspec.registry not importable).", {}
        source_ref, _artifact_ref = registry.parse_identifier(identifier)
        source = registry.get_source_by_name(source_ref) or registry.get_source(source_ref)
        if source is None:
            return None, f"No registered OpenSpec source for '{source_ref}'.", {}
        root = Path(source["path"]).expanduser()
        if not root.is_absolute():
            root = root.resolve()
        if not root.exists() or not root.is_dir():
            return None, f"registered source path does not exist or is not a directory: {root}", {}
        return root, None, {"source": source, "name": registry.effective_name(source)}

    root, err = _resolve_workdir(None)
    return root, err, {}


def _ensure_openspec_layout(root: Path) -> None:
    openspec_root = root / "openspec"
    (openspec_root / "changes" / "archive").mkdir(parents=True, exist_ok=True)
    (openspec_root / "specs").mkdir(parents=True, exist_ok=True)
    (openspec_root / "ideas").mkdir(parents=True, exist_ok=True)


def _unique_idea_path(ideas_root: Path, slug: str) -> tuple[str, Path]:
    candidate = ideas_root / f"{slug}.md"
    if not candidate.exists():
        return slug, candidate
    index = 2
    while True:
        suffixed = f"{slug}-{index}"
        candidate = ideas_root / f"{suffixed}.md"
        if not candidate.exists():
            return suffixed, candidate
        index += 1


def _coerce_string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _idea_path(root: Path, idea_ref: str) -> Path:
    slug = _slugify(idea_ref)
    return root / "openspec" / "ideas" / f"{slug}.md"


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _markdown_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


_TASK_LINE_RE = re.compile(r"^(?P<prefix>\s*- \[)(?P<mark>[ xX])(?P<suffix>\]\s*(?P<id>\d+(?:\.\d+)*)\s+(?P<text>.*?))\s*$")


def _change_path(root: Path, change: str, *, archived: bool = False) -> Path:
    base = root / "openspec" / "changes"
    if archived:
        base = base / "archive"
    return base / change


def _resolve_change_path(root: Path, change_ref: str) -> tuple[Path | None, bool]:
    change = _slugify(change_ref, fallback="")
    if not change:
        return None, False
    active = _change_path(root, change)
    if active.is_dir():
        return active, False
    archived = _change_path(root, change, archived=True)
    if archived.is_dir():
        return archived, True
    return None, False


def _derive_status(tasks_path: Path, *, archived: bool = False) -> str:
    if archived:
        return "archived"
    if not tasks_path.is_file():
        return "draft"
    tasks = _parse_tasks(tasks_path)
    if not tasks:
        return "draft"
    done = sum(1 for task in tasks if task["status"] == "done")
    if done == 0:
        return "todo"
    if done == len(tasks):
        return "done"
    return "in_progress"


def _parse_tasks(tasks_path: Path) -> list[dict[str, Any]]:
    if not tasks_path.is_file():
        return []
    tasks: list[dict[str, Any]] = []
    for line_no, line in enumerate(tasks_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        match = _TASK_LINE_RE.match(line)
        if not match:
            continue
        tasks.append({
            "id": match.group("id"),
            "text": match.group("text").strip(),
            "status": "done" if match.group("mark").lower() == "x" else "todo",
            "line": line_no,
        })
    return tasks


def _task_counts(tasks: list[dict[str, Any]]) -> dict[str, int]:
    done = sum(1 for task in tasks if task["status"] == "done")
    total = len(tasks)
    return {"total": total, "done": done, "todo": total - done}


def _format_tasks(items: list[str]) -> str:
    lines = ["## 1. Tasks", ""]
    for index, text in enumerate(items, start=1):
        lines.append(f"- [ ] 1.{index} {text}")
    lines.append("")
    return "\n".join(lines)


def _default_tasks() -> list[str]:
    return ["Refine scope", "Implement behavior", "Validate OpenSpec artifacts and tests"]


def _write_placeholder_spec(change_dir: Path, change: str, title: str, source: str = "change") -> Path:
    spec_dir = change_dir / "specs" / change
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_path = spec_dir / "spec.md"
    if spec_path.exists():
        return spec_path
    spec = f"""# {title}

## ADDED Requirements

### Requirement: {title} scope
The system SHALL implement the approved behavior described by this {source} after this placeholder is refined into concrete requirements.

#### Scenario: Placeholder refinement
- **GIVEN** `{change}` has been created as an OpenSpec change
- **WHEN** implementation begins
- **THEN** this placeholder requirement is replaced or refined with concrete, testable behavior before the change is completed
"""
    spec_path.write_text(spec, encoding="utf-8")
    return spec_path


def _write_change_scaffold(
    root: Path,
    change: str,
    title: str,
    summary: str,
    *,
    source_section: str = "",
    tasks: list[str] | None = None,
    with_spec: bool = False,
    force: bool = False,
) -> tuple[dict[str, Any] | None, str | None]:
    _ensure_openspec_layout(root)
    change_dir = _change_path(root, change)
    if change_dir.exists() and not force:
        return None, f"change already exists: {change}"
    change_dir.mkdir(parents=True, exist_ok=True)
    created = _now_iso()
    source_block = f"\n## Source\n\n{source_section}\n" if source_section else ""
    proposal = f"""## Why

{summary}

## What Changes

- Create the `{change}` OpenSpec change scaffold for review and refinement.

{source_block}## Capabilities

### New Capabilities
- `{change}`: Initial capability placeholder. Refine before implementation.

### Modified Capabilities
- None yet.

## Impact

- TBD: Fill in affected code, APIs, dependencies, or systems before implementation.
"""
    (change_dir / "proposal.md").write_text(proposal, encoding="utf-8")
    task_items = tasks or []
    if task_items:
        (change_dir / "tasks.md").write_text(_format_tasks(task_items), encoding="utf-8")
    spec_path = None
    if with_spec:
        spec_path = _write_placeholder_spec(change_dir, change, title)
    (change_dir / ".openspec.yaml").write_text(
        "schema: spec-driven\ncreatedAt: " + json.dumps(created) + "\n",
        encoding="utf-8",
    )
    paths = {
        "proposal": str(change_dir / "proposal.md"),
        "metadata": str(change_dir / ".openspec.yaml"),
    }
    if task_items:
        paths["tasks"] = str(change_dir / "tasks.md")
    if spec_path:
        paths["spec"] = str(spec_path)
    return {
        "ok": True,
        "change": change,
        "change_path": str(change_dir),
        "relative_change_path": _relative(change_dir, root),
        "workdir": str(root),
        "status": _derive_status(change_dir / "tasks.md"),
        "paths": paths,
    }, None


def openspec_idea_create(args: dict, **kwargs) -> str:
    root, err, context = _resolve_project(args)
    if err or root is None:
        return _error(err or "workdir could not be resolved")

    title = str(args.get("title") or "").strip()
    prompt = str(args.get("prompt") or "").strip()
    if not title:
        return _error("title is required")
    if not prompt:
        return _error("prompt is required")

    origin = str(args.get("origin") or args.get("source") or "unspecified").strip() or "unspecified"
    notes = str(args.get("notes") or "").strip()
    tags = _coerce_string_list(args.get("tags"))

    _ensure_openspec_layout(root)
    ideas_root = root / "openspec" / "ideas"
    slug, path = _unique_idea_path(ideas_root, _slugify(str(args.get("slug") or title)))
    created = _now_iso()
    tags_text = ", ".join(tags) if tags else "None"

    sections = [
        f"# {title}",
        "",
        "## Source",
        f"- Origin: {origin}",
        f"- Created: {created}",
        f"- Tags: {tags_text}",
    ]
    if context.get("name"):
        sections.append(f"- Project: {context['name']}")
    sections.extend([
        "",
        "## Prompt",
        prompt,
    ])
    if notes:
        sections.extend(["", "## Notes", notes])
    sections.append("")

    path.write_text("\n".join(sections), encoding="utf-8")
    return json.dumps({
        "ok": True,
        "slug": slug,
        "title": title,
        "path": str(path),
        "relative_path": _relative(path, root),
        "workdir": str(root),
        "metadata": {"origin": origin, "created": created, "tags": tags},
    })


def openspec_idea_enrich(args: dict, **kwargs) -> str:
    root, err, _context = _resolve_project(args)
    if err or root is None:
        return _error(err or "workdir could not be resolved")
    idea = str(args.get("idea") or args.get("slug") or "").strip()
    if not idea:
        return _error("idea is required")

    path = _idea_path(root, idea)
    if not path.is_file():
        return _error(f"idea not found: {idea}")

    feasibility = str(args.get("feasibility") or "").strip()
    tshirt_size = str(args.get("tshirt_size") or args.get("t_shirt_size") or "").strip()
    if feasibility and feasibility.lower() not in _VALID_FEASIBILITY:
        return _error("feasibility must be one of: Low, Medium, High")
    if tshirt_size and tshirt_size.lower() not in _VALID_TSHIRT:
        return _error("tshirt_size must be one of: XS, S, M, L, XL")

    problem = str(args.get("problem") or "TBD").strip() or "TBD"
    proposed_direction = str(args.get("proposed_direction") or args.get("proposedDirection") or "TBD").strip() or "TBD"
    key_questions = _coerce_string_list(args.get("key_questions"))
    risks = _coerce_string_list(args.get("risks"))
    size_justification = str(args.get("size_justification") or "TBD").strip() or "TBD"
    suggested_next_step = str(args.get("suggested_next_step") or "TBD").strip() or "TBD"
    generated = _now_iso()

    report = "\n".join([
        _ENRICHMENT_START,
        "## Enrichment Report",
        "",
        f"Generated: {generated}",
        "",
        "### Problem",
        problem,
        "",
        "### Proposed Direction",
        proposed_direction,
        "",
        "### Key Questions",
        _markdown_list(key_questions),
        "",
        "### Feasibility",
        f"Feasibility: {feasibility or 'TBD'}",
        "",
        "### T-Shirt Size",
        f"T-Shirt Size: {tshirt_size or 'TBD'}",
        "",
        "### Size Justification",
        size_justification,
        "",
        "### Risks",
        _markdown_list(risks),
        "",
        "### Suggested Next Step",
        suggested_next_step,
        _ENRICHMENT_END,
        "",
    ])

    content = path.read_text(encoding="utf-8", errors="replace")
    if _ENRICHMENT_START in content and _ENRICHMENT_END in content:
        before, rest = content.split(_ENRICHMENT_START, 1)
        _old, after = rest.split(_ENRICHMENT_END, 1)
        content = before.rstrip() + "\n\n" + report + after.lstrip("\n")
    else:
        content = content.rstrip() + "\n\n" + report
    path.write_text(content, encoding="utf-8")

    return json.dumps({
        "ok": True,
        "idea": _slugify(idea),
        "path": str(path),
        "relative_path": _relative(path, root),
        "workdir": str(root),
        "metadata": {"generated": generated, "feasibility": feasibility, "tshirt_size": tshirt_size},
    })


def openspec_idea_promote(args: dict, **kwargs) -> str:
    root, err, _context = _resolve_project(args)
    if err or root is None:
        return _error(err or "workdir could not be resolved")
    idea = str(args.get("idea") or args.get("slug") or "").strip()
    change = _slugify(str(args.get("change") or args.get("change_id") or ""), fallback="")
    if not idea:
        return _error("idea is required")
    if not change or not _VALID_CHANGE_RE.match(change):
        return _error("change must be a kebab-case id")

    idea_path = _idea_path(root, idea)
    if not idea_path.is_file():
        return _error(f"idea not found: {idea}")

    _ensure_openspec_layout(root)
    change_dir = root / "openspec" / "changes" / change
    if change_dir.exists() and not args.get("force"):
        return _error(f"change already exists: {change}", change=change, change_path=str(change_dir))
    change_dir.mkdir(parents=True, exist_ok=True)

    idea_content = idea_path.read_text(encoding="utf-8", errors="replace")
    title = idea_content.splitlines()[0].lstrip("# ").strip() if idea_content.strip() else idea
    summary = str(args.get("summary") or f"Promote idea: {title}").strip()
    rel_idea = _relative(idea_path, root)
    created = _now_iso()

    proposal = f"""## Why

{summary}

## What Changes

- Promote the reviewed idea `{idea_path.stem}` into an implementation-ready OpenSpec change.
- Preserve traceability to the source idea while proposal, specs, design, and tasks are refined.

## Source Idea

- Path: `{rel_idea}`
- Promoted: {created}

### Idea Content

```md
{idea_content.rstrip()}
```

## Capabilities

### New Capabilities
- `{change}`: Initial capability placeholder created from the promoted idea. Refine before implementation.

### Modified Capabilities
- None yet.

## Impact

- TBD: Fill in affected code, APIs, dependencies, or systems before implementation.
"""
    tasks = """## 1. Proposal Refinement

- [ ] 1.1 Review the source idea and clarify scope.
- [ ] 1.2 Identify affected capabilities and write spec deltas.
- [ ] 1.3 Add design notes if implementation trade-offs are non-trivial.

## 2. Implementation

- [ ] 2.1 Implement the approved behavior.
- [ ] 2.2 Add or update tests.
- [ ] 2.3 Validate OpenSpec artifacts and test suite.
"""
    spec_dir = change_dir / "specs" / change
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec = f"""# {title}

## ADDED Requirements

### Requirement: Promoted idea scope
The system SHALL implement the approved behavior described by the promoted idea after this placeholder is refined into concrete requirements.

#### Scenario: Placeholder refinement
- **GIVEN** the idea `{idea_path.stem}` has been promoted into this change
- **WHEN** implementation begins
- **THEN** this placeholder requirement is replaced or refined with concrete, testable behavior before the change is completed
"""
    (change_dir / "proposal.md").write_text(proposal, encoding="utf-8")
    (change_dir / "tasks.md").write_text(tasks, encoding="utf-8")
    (spec_dir / "spec.md").write_text(spec, encoding="utf-8")
    metadata = {
        "schema": "spec-driven",
        "sourceIdea": rel_idea,
        "promotedAt": created,
    }
    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\nsourceIdea: " + json.dumps(rel_idea) + "\npromotedAt: " + json.dumps(created) + "\n", encoding="utf-8")

    return json.dumps({
        "ok": True,
        "idea": idea_path.stem,
        "change": change,
        "change_path": str(change_dir),
        "relative_change_path": _relative(change_dir, root),
        "workdir": str(root),
        "paths": {
            "proposal": str(change_dir / "proposal.md"),
            "tasks": str(change_dir / "tasks.md"),
            "spec": str(spec_dir / "spec.md"),
            "metadata": str(change_dir / ".openspec.yaml"),
        },
        "metadata": metadata,
    })


def openspec_change_create(args: dict, **kwargs) -> str:
    root, err, _context = _resolve_project(args)
    if err or root is None:
        return _error(err or "workdir could not be resolved")
    change = _slugify(str(args.get("change") or args.get("change_id") or ""), fallback="")
    title = str(args.get("title") or change.replace("-", " ").title()).strip()
    summary = str(args.get("summary") or f"Create change: {title}").strip()
    if not change or not _VALID_CHANGE_RE.match(change):
        return _error("change must be a kebab-case id")
    tasks = _coerce_string_list(args.get("tasks"))
    result, error = _write_change_scaffold(
        root,
        change,
        title,
        summary,
        tasks=tasks,
        with_spec=bool(args.get("with_spec")) or bool(tasks),
        force=bool(args.get("force")),
    )
    if error:
        return _error(error, change=change, change_path=str(_change_path(root, change)))
    return json.dumps(result)


def openspec_change_promote(args: dict, **kwargs) -> str:
    root, err, _context = _resolve_project(args)
    if err or root is None:
        return _error(err or "workdir could not be resolved")
    change = _slugify(str(args.get("change") or args.get("change_id") or ""), fallback="")
    if not change:
        return _error("change is required")
    change_dir, archived = _resolve_change_path(root, change)
    if change_dir is None or archived:
        return _error(f"active change not found: {change}")
    tasks_path = change_dir / "tasks.md"
    if not tasks_path.exists() or bool(args.get("replace_tasks")):
        task_items = _coerce_string_list(args.get("tasks")) or _default_tasks()
        tasks_path.write_text(_format_tasks(task_items), encoding="utf-8")
    title = change.replace("-", " ").title()
    proposal = _read_doc(change_dir / "proposal.md")
    for line in proposal.splitlines():
        if line.startswith("# "):
            title = line.lstrip("# ").strip() or title
            break
    spec_path = _write_placeholder_spec(change_dir, change, title)
    tasks = _parse_tasks(tasks_path)
    return json.dumps({
        "ok": True,
        "change": change,
        "change_path": str(change_dir),
        "relative_change_path": _relative(change_dir, root),
        "workdir": str(root),
        "status": _derive_status(tasks_path),
        "counts": _task_counts(tasks),
        "paths": {"tasks": str(tasks_path), "spec": str(spec_path)},
    })


def openspec_task_list(args: dict, **kwargs) -> str:
    root, err, _context = _resolve_project(args)
    if err or root is None:
        return _error(err or "workdir could not be resolved")
    change = _slugify(str(args.get("change") or args.get("change_id") or ""), fallback="")
    if not change:
        return _error("change is required")
    change_dir, archived = _resolve_change_path(root, change)
    if change_dir is None:
        return _error(f"change not found: {change}")
    tasks_path = change_dir / "tasks.md"
    tasks = _parse_tasks(tasks_path)
    if not tasks:
        return _error(f"tasks not found for change: {change}", change=change, tasks=[])
    return json.dumps({
        "ok": True,
        "change": change,
        "archived": archived,
        "path": str(tasks_path),
        "relative_path": _relative(tasks_path, root),
        "tasks": tasks,
        "counts": _task_counts(tasks),
        "status": _derive_status(tasks_path, archived=archived),
    })


def openspec_task_set_status(args: dict, **kwargs) -> str:
    root, err, _context = _resolve_project(args)
    if err or root is None:
        return _error(err or "workdir could not be resolved")
    change = _slugify(str(args.get("change") or args.get("change_id") or ""), fallback="")
    status = str(args.get("status") or "").strip().lower()
    if status in {"open", "todo", "pending"}:
        mark = " "
        normalized = "todo"
    elif status in {"done", "complete", "completed"}:
        mark = "x"
        normalized = "done"
    else:
        return _error("status must be 'todo' or 'done'")
    task_ids = set(_coerce_string_list(args.get("tasks") or args.get("task_ids")))
    if not task_ids:
        return _error("tasks is required")
    change_dir, archived = _resolve_change_path(root, change)
    if change_dir is None or archived:
        return _error(f"active change not found: {change}")
    tasks_path = change_dir / "tasks.md"
    if not tasks_path.is_file():
        return _error(f"tasks not found for change: {change}")
    lines = tasks_path.read_text(encoding="utf-8", errors="replace").splitlines()
    found: set[str] = set()
    updated_lines = []
    for line in lines:
        match = _TASK_LINE_RE.match(line)
        if match and match.group("id") in task_ids:
            found.add(match.group("id"))
            line = f"{match.group('prefix')}{mark}{match.group('suffix')}"
        updated_lines.append(line)
    missing = sorted(task_ids - found)
    if missing:
        return _error("task ids not found: " + ", ".join(missing), missing=missing)
    tasks_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    tasks = _parse_tasks(tasks_path)
    return json.dumps({
        "ok": True,
        "change": change,
        "updated": sorted(found),
        "set_status": normalized,
        "path": str(tasks_path),
        "relative_path": _relative(tasks_path, root),
        "tasks": tasks,
        "counts": _task_counts(tasks),
        "status": _derive_status(tasks_path),
    })


def openspec_change_archive(args: dict, **kwargs) -> str:
    root, err, _context = _resolve_project(args)
    if err or root is None:
        return _error(err or "workdir could not be resolved")
    change = _slugify(str(args.get("change") or args.get("change_id") or ""), fallback="")
    if not change:
        return _error("change is required")
    change_dir = _change_path(root, change)
    if not change_dir.is_dir():
        return _error(f"active change not found: {change}")
    tasks_path = change_dir / "tasks.md"
    status = _derive_status(tasks_path)
    if status != "done" and not args.get("force"):
        return _error(f"change is not complete: {change}", status=status)
    archive_dir = _change_path(root, change, archived=True)
    archive_dir.parent.mkdir(parents=True, exist_ok=True)
    if archive_dir.exists() and not args.get("force"):
        return _error(f"archived change already exists: {change}")
    if archive_dir.exists():
        shutil.rmtree(archive_dir)
    shutil.move(str(change_dir), str(archive_dir))
    return json.dumps({
        "ok": True,
        "change": change,
        "status": "archived",
        "archived_path": str(archive_dir),
        "relative_archived_path": _relative(archive_dir, root),
        "workdir": str(root),
    })


def openspec_change_unarchive(args: dict, **kwargs) -> str:
    root, err, _context = _resolve_project(args)
    if err or root is None:
        return _error(err or "workdir could not be resolved")
    change = _slugify(str(args.get("change") or args.get("change_id") or ""), fallback="")
    if not change:
        return _error("change is required")
    archive_dir = _change_path(root, change, archived=True)
    active_dir = _change_path(root, change)
    if not archive_dir.is_dir():
        return _error(f"archived change not found: {change}")
    if active_dir.exists() and not args.get("force"):
        return _error(f"active change already exists: {change}")
    if active_dir.exists():
        shutil.rmtree(active_dir)
    shutil.move(str(archive_dir), str(active_dir))
    status = _derive_status(active_dir / "tasks.md")
    return json.dumps({
        "ok": True,
        "change": change,
        "status": status,
        "change_path": str(active_dir),
        "relative_change_path": _relative(active_dir, root),
        "workdir": str(root),
    })


def openspec_list(args: dict, **kwargs) -> str:
    cmd = ["list", "--json"]
    kind = str(args.get("kind") or "changes").strip().lower()
    if kind == "specs":
        cmd.append("--specs")
    else:
        cmd.append("--changes")
    sort = str(args.get("sort") or "").strip().lower()
    if sort in {"recent", "name"}:
        cmd.extend(["--sort", sort])
    return _run(cmd, args.get("workdir"))


def openspec_show(args: dict, **kwargs) -> str:
    name = str(args.get("name") or "").strip()
    if not name:
        return json.dumps({"ok": False, "error": "name is required"})
    cmd = ["show", name, "--json", "--no-interactive"]
    item_type = str(args.get("type") or "").strip().lower()
    if item_type in {"change", "spec"}:
        cmd.extend(["--type", item_type])
    if args.get("deltas_only"):
        cmd.append("--deltas-only")
    if args.get("requirements_only"):
        cmd.append("--requirements")
    if args.get("no_scenarios"):
        cmd.append("--no-scenarios")
    requirement = str(args.get("requirement") or "").strip()
    if requirement:
        cmd.extend(["--requirement", requirement])
    return _run(cmd, args.get("workdir"))


def openspec_validate(args: dict, **kwargs) -> str:
    cmd = ["validate", "--json", "--no-interactive"]
    if args.get("strict", True):
        cmd.append("--strict")
    scope = str(args.get("scope") or "").strip().lower()
    target = str(args.get("target") or "").strip()
    if scope == "all" or (not target and not scope):
        cmd.append("--all")
    elif scope == "changes":
        cmd.append("--changes")
    elif scope == "specs":
        cmd.append("--specs")
    elif target:
        cmd.append(target)
    else:
        return json.dumps({"ok": False, "error": "target is required when scope='target'"})
    item_type = str(args.get("type") or "").strip().lower()
    if item_type in {"change", "spec"}:
        cmd.extend(["--type", item_type])
    return _run(cmd, args.get("workdir"))


def openspec_status(args: dict, **kwargs) -> str:
    change = str(args.get("change") or "").strip()
    if not change:
        return json.dumps({"ok": False, "error": "change is required"})
    cmd = ["status", "--change", change, "--json"]
    schema = str(args.get("schema") or "").strip()
    if schema:
        cmd.extend(["--schema", schema])
    return _run(cmd, args.get("workdir"))


def openspec_instructions(args: dict, **kwargs) -> str:
    cmd = ["instructions", "--json"]
    artifact = _normalize_artifact(str(args.get("artifact") or ""))
    if artifact:
        cmd.append(artifact)
    change = str(args.get("change") or "").strip()
    if change:
        cmd.extend(["--change", change])
    schema = str(args.get("schema") or "").strip()
    if schema:
        cmd.extend(["--schema", schema])

    result = _run(cmd, args.get("workdir"))
    parsed = json.loads(result)
    if parsed.get("ok"):
        return result
    reason = "\n".join(str(parsed.get(key) or "") for key in ("stderr", "stdout", "error"))
    fallback = _template_instruction_fallback(artifact, reason, args.get("workdir"), schema)
    return fallback or result

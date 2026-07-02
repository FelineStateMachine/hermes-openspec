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
        change_dirs = [(change_dir, archived) for change_dir, archived in _iter_change_dirs(repo_path) if not archived]
        sequence = {}
        if hasattr(registry, "ensure_change_sequence"):
            sequence = registry.ensure_change_sequence(str(source.get("id") or source.get("token")), [change_dir.name for change_dir, _ in change_dirs])
        changes = [
            {
                "name": change_dir.name,
                "token": registry.change_token(change_dir.name),
                **({"sequence": sequence[change_dir.name]} if change_dir.name in sequence else {}),
            }
            for change_dir, archived in change_dirs
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


_TASK_LINE_RE = re.compile(r"^(?P<prefix>\s*- \[)(?P<mark>[ xX])(?P<suffix>\]\s*(?:(?P<id>\d+(?:\.\d+)*)\s+)?(?P<text>.*?))\s*$")


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


def _resolve_change_names(root: Path, registry, refs: list[str]) -> tuple[list[str], list[str]]:
    names: list[str] = []
    missing: list[str] = []
    by_name = {change_dir.name: change_dir.name for change_dir, _ in _iter_change_dirs(root)}
    by_token = {registry.change_token(name): name for name in by_name}
    for ref in refs:
        raw = str(ref or "").strip()
        if not raw:
            continue
        name = by_name.get(raw) or by_token.get(raw)
        if name:
            if name not in names:
                names.append(name)
        else:
            missing.append(raw)
    return names, missing


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
    seq = 0
    for line_no, line in enumerate(tasks_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        match = _TASK_LINE_RE.match(line)
        if not match:
            continue
        seq += 1
        task_id = match.group("id") or str(seq)
        tasks.append({
            "id": task_id,
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


def openspec_change_sequence_set(args: dict, **kwargs) -> str:
    """Set dashboard-local order/dependency metadata for active changes."""
    root, err, context = _resolve_project(args)
    if err or root is None:
        return _error(err or "workdir could not be resolved")
    registry = _registry_module()
    if registry is None or not hasattr(registry, "set_change_sequence"):
        return _error("OpenSpec registry sequence support unavailable")
    source = context.get("source") if isinstance(context, dict) else None
    if source is None:
        source = registry.get_source_by_path(str(root))
    if source is None:
        return _error("sequence metadata requires a registered OpenSpec source; pass identifier/project or register the repo in the dashboard", workdir=str(root))
    raw_changes = _coerce_string_list(args.get("changes"))
    changes, missing = _resolve_change_names(root, registry, raw_changes)
    if missing:
        return _error("some changes were not found", missing=missing, workdir=str(root))
    if not changes:
        return _error("changes is required")
    raw_deps = args.get("dependencies") or args.get("depends_on") or {}
    if raw_deps is None:
        raw_deps = {}
    if not isinstance(raw_deps, dict):
        return _error("dependencies must be an object mapping change names/tokens to arrays of prerequisite change names/tokens")
    dependencies: dict[str, list[str]] = {}
    dep_missing: list[str] = []
    for raw_key, raw_values in raw_deps.items():
        key_names, key_missing = _resolve_change_names(root, registry, [str(raw_key)])
        dep_names, missing_deps = _resolve_change_names(root, registry, _coerce_string_list(raw_values))
        if key_missing:
            dep_missing.extend(key_missing)
            continue
        if missing_deps:
            dep_missing.extend(missing_deps)
        if key_names:
            dependencies[key_names[0]] = dep_names
    if dep_missing:
        return _error("some dependency changes were not found", missing=dep_missing, workdir=str(root))
    source_id = str(source.get("id") or source.get("token"))
    group_id = str(args.get("group_id") or args.get("groupId") or "default").strip() or "default"
    sequence = registry.set_change_sequence(source_id, changes, group_id=group_id, dependencies=dependencies)
    return json.dumps({
        "ok": True,
        "source": registry.effective_name(source),
        "source_id": source_id,
        "workdir": str(root),
        "groupId": group_id,
        "changes": [{"name": name, "token": registry.change_token(name), "sequence": sequence.get(name, {})} for name in changes],
        "note": "Sequence/dependency metadata is stored in the Hermes OpenSpec plugin DB, not in OpenSpec files.",
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
    # Build a lookup of parsed tasks so we can match by numeric ID or text substring.
    parsed = _parse_tasks(tasks_path)
    # Resolve each requested task_id to actual line numbers.
    # Accept: numeric IDs (exact match), or text substrings (case-insensitive).
    target_lines: set[int] = set()
    not_found: list[str] = []
    for requested in task_ids:
        # Try exact numeric ID match first
        id_matches = [t for t in parsed if t["id"] == requested]
        if id_matches:
            for t in id_matches:
                target_lines.add(t["line"])
            continue
        # Try text substring match (case-insensitive)
        needle = requested.lower()
        text_matches = [t for t in parsed if needle in t["text"].lower()]
        if text_matches:
            for t in text_matches:
                target_lines.add(t["line"])
            continue
        not_found.append(requested)
    if not_found:
        return _error("task ids not found: " + ", ".join(not_found), missing=not_found)
    # Rewrite matching lines
    updated_lines = []
    matched_ids: set[str] = set()
    for line_no, line in enumerate(lines, start=1):
        if line_no in target_lines:
            match = _TASK_LINE_RE.match(line)
            if match:
                matched_ids.add(match.group("id") or str(line_no))
                line = f"{match.group('prefix')}{mark}{match.group('suffix')}"
        updated_lines.append(line)
    tasks_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    tasks = _parse_tasks(tasks_path)
    return json.dumps({
        "ok": True,
        "change": change,
        "updated": sorted(matched_ids),
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


def openspec_spec_diff(args: dict, **kwargs) -> str:
    """Compare a change's delta spec against its baseline, or a worktree spec
    against its HEAD version, and return the structured semantic delta plus a
    unified line diff fallback.

    Filesystem-backed — does not require the OpenSpec CLI binary.
    """
    root, err, _context = _resolve_project(args)
    if err or root is None:
        return _error(err or "workdir could not be resolved")

    spec = str(args.get("spec") or "").strip()
    if not spec:
        return _error("spec is required (e.g. 'agent-tools')")

    # Prevent path traversal
    if spec.startswith("/") or ".." in Path(spec).parts:
        return _error("spec must be a relative path without parent references")

    change = str(args.get("change") or "").strip()

    try:
        from . import spec_parser  # type: ignore
    except ImportError:
        import spec_parser  # type: ignore

    if change:
        # Diff change spec vs baseline
        change_spec_path = root / "openspec" / "changes" / change / "specs" / f"{spec}" / "spec.md"
        # Also handle nested paths like "agent-tools/spec.md"
        if not change_spec_path.is_file():
            change_spec_path = root / "openspec" / "changes" / change / "specs" / f"{spec}.md"
        if not change_spec_path.is_file():
            return _error(
                f"change spec not found: openspec/changes/{change}/specs/{spec}/spec.md",
                change=change,
                spec=spec,
            )

        after_md = _read_doc(change_spec_path)
        baseline_path = root / "openspec" / "specs" / spec / "spec.md"
        if not baseline_path.is_file():
            baseline_path = root / "openspec" / "specs" / f"{spec}.md"

        before_md = _read_doc(baseline_path) if baseline_path.is_file() else None
        baseline_exists = before_md is not None
    else:
        # Diff worktree spec vs HEAD
        worktree_path = root / "openspec" / "specs" / spec / "spec.md"
        if not worktree_path.is_file():
            worktree_path = root / "openspec" / "specs" / f"{spec}.md"
        if not worktree_path.is_file():
            return _error(
                f"spec not found: openspec/specs/{spec}/spec.md",
                spec=spec,
            )

        after_md = _read_doc(worktree_path)
        before_md = _git_show_spec(root, spec)
        if before_md is None:
            return _error(
                "git is required for worktree-vs-HEAD comparison and the spec "
                "has no git history (it may be untracked). Pass 'change' to "
                "diff against a change's delta spec instead.",
                spec=spec,
            )
        baseline_exists = True

    diff = spec_parser.semantic_spec_diff(before_md, after_md)
    line_diff = spec_parser.unified_diff(before_md, after_md, spec)

    return json.dumps({
        "ok": True,
        "spec": spec,
        "change": change or None,
        "status": diff["status"],
        "baseline_exists": baseline_exists,
        "requirements": diff["requirements"],
        "line_diff": line_diff,
        "workdir": str(root),
    })


def _git_show_spec(root: Path, spec_path: str) -> str | None:
    """Return the HEAD version of a spec via git, or None if unavailable."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "show", f"HEAD:openspec/specs/{spec_path}/spec.md"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        # Try flat path
        try:
            proc = subprocess.run(
                ["git", "-C", str(root), "show", f"HEAD:openspec/specs/{spec_path}.md"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except Exception:
            return None
        if proc.returncode != 0:
            return None
    return proc.stdout


def _spec_target_path(root: Path, spec: str, change: str) -> Path:
    """Resolve the spec.md path for a given spec name and optional change scope."""
    if change:
        base = root / "openspec" / "changes" / change / "specs"
    else:
        base = root / "openspec" / "specs"
    return base / spec / "spec.md"


def _spec_dir_from_path(spec_path: Path) -> str:
    """Extract the spec directory name from a spec.md path."""
    return spec_path.parent.name


def _list_specs_in_dir(specs_root: Path) -> list[str]:
    """List spec names (directory names containing spec.md) under a specs root."""
    if not specs_root.is_dir():
        return []
    names: list[str] = []
    for child in sorted(specs_root.iterdir()):
        if child.is_dir() and (child / "spec.md").is_file():
            names.append(child.name)
        elif child.is_file() and child.suffix == ".md" and child.name != "spec.md":
            # Flat .md files at the root level
            names.append(child.stem)
    return names


def openspec_spec_create(args: dict, **kwargs) -> str:
    """Create a spec from structured input and write a formatted spec.md.

    Filesystem-backed — does not require the OpenSpec CLI binary.
    """
    root, err, _context = _resolve_project(args)
    if err or root is None:
        return _error(err or "workdir could not be resolved")

    spec = str(args.get("spec") or "").strip()
    if not spec:
        return _error("spec is required (e.g. 'agent-tools')")

    # Validate slug: kebab-case, no path traversal
    if not _VALID_CHANGE_RE.match(spec) or ".." in Path(spec).parts or spec.startswith("/"):
        return _error(f"spec must be kebab-case (letters, numbers, hyphens): {spec}")

    title = str(args.get("title") or "").strip()
    if not title:
        return _error("title is required")

    purpose = str(args.get("purpose") or "").strip()
    if not purpose:
        return _error("purpose is required")

    requirements = args.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        return _error("requirements must be a non-empty array")

    change = str(args.get("change") or "").strip()
    if change and not _VALID_CHANGE_RE.match(change):
        return _error(f"change must be kebab-case: {change}")

    force = bool(args.get("force"))

    spec_path = _spec_target_path(root, spec, change)

    if spec_path.exists() and not force:
        rel = _relative(spec_path, root)
        return _error(
            f"spec already exists at {rel}. Pass force=true to overwrite.",
            spec=spec,
            change=change or None,
            path=rel,
        )

    try:
        from . import spec_parser  # type: ignore
    except ImportError:
        import spec_parser  # type: ignore

    md = spec_parser.spec_to_markdown(title, purpose, requirements)

    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(md, encoding="utf-8")

    return json.dumps({
        "ok": True,
        "spec": spec,
        "change": change or None,
        "path": _relative(spec_path, root),
        "absolute_path": str(spec_path),
        "workdir": str(root),
    })


def openspec_spec_show(args: dict, **kwargs) -> str:
    """Read a spec as structured JSON using parse_spec.

    Filesystem-backed — does not require the OpenSpec CLI binary.
    """
    root, err, _context = _resolve_project(args)
    if err or root is None:
        return _error(err or "workdir could not be resolved")

    spec = str(args.get("spec") or "").strip()
    if not spec:
        return _error("spec is required (e.g. 'agent-tools')")

    if spec.startswith("/") or ".." in Path(spec).parts:
        return _error("spec must be a relative path without parent references")

    change = str(args.get("change") or "").strip()

    spec_path = _spec_target_path(root, spec, change)
    if not spec_path.is_file():
        # Try flat .md path
        if change:
            flat = root / "openspec" / "changes" / change / "specs" / f"{spec}.md"
        else:
            flat = root / "openspec" / "specs" / f"{spec}.md"
        if flat.is_file():
            spec_path = flat
        else:
            location = f"openspec/changes/{change}/specs/{spec}/spec.md" if change else f"openspec/specs/{spec}/spec.md"
            return _error(f"spec not found: {location}", spec=spec, change=change or None)

    try:
        from . import spec_parser  # type: ignore
    except ImportError:
        import spec_parser  # type: ignore

    md = _read_doc(spec_path)
    parsed = spec_parser.parse_spec(md)

    return json.dumps({
        "ok": True,
        "spec": spec,
        "change": change or None,
        "path": _relative(spec_path, root),
        "title": parsed["title"],
        "purpose": parsed["purpose"],
        "requirements": parsed["requirements"],
        "workdir": str(root),
    })


def openspec_spec_list(args: dict, **kwargs) -> str:
    """List specs within a change, or baseline specs.

    Filesystem-backed — does not require the OpenSpec CLI binary.
    """
    root, err, _context = _resolve_project(args)
    if err or root is None:
        return _error(err or "workdir could not be resolved")

    change = str(args.get("change") or "").strip()

    if change:
        if not _VALID_CHANGE_RE.match(change):
            return _error(f"change must be kebab-case: {change}")
        specs_root = root / "openspec" / "changes" / change / "specs"
    else:
        specs_root = root / "openspec" / "specs"

    names = _list_specs_in_dir(specs_root)

    return json.dumps({
        "ok": True,
        "change": change or None,
        "specs": names,
        "count": len(names),
        "workdir": str(root),
    })


def openspec_cli(args: dict, **kwargs) -> str:
    """Run the openspec CLI binary directly and return raw output.

    This is a passthrough tool — it runs ``openspec <command> [--json]`` and
    returns the raw stdout. Use this when you need the CLI's native JSON format
    (e.g. ``applyRequires``, ``artifacts``, ``contextFiles``) rather than the
    plugin's wrapped JSON shapes.

    Gated by ``check_fn`` — only appears when the openspec binary is available.
    """
    import shlex

    exe = _openspec_bin()
    if exe is None:
        return _error("openspec CLI binary not found. Set OPENSPEC_BIN or install via npm.")

    raw_command = str(args.get("command") or "").strip()
    if not raw_command:
        return _error("command is required (e.g. 'status --change my-change')")

    try:
        cmd_parts = shlex.split(raw_command)
    except ValueError:
        cmd_parts = raw_command.split()

    json_output = args.get("json_output")
    if json_output is None:
        json_output = True
    if json_output:
        cmd_parts = [*cmd_parts, "--json"]

    workdir = str(args.get("workdir") or "").strip()
    if workdir:
        root, err = _resolve_workdir(workdir)
        if err or root is None:
            return _error(err or "workdir could not be resolved")
        cwd = str(root)
    else:
        cwd = None

    try:
        proc = subprocess.run(
            [exe, *cmd_parts],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return _error("openspec CLI command timed out (120s)")
    except OSError as exc:
        return _error(f"failed to run openspec CLI: {exc}")

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    if json_output and proc.returncode == 0:
        try:
            parsed = json.loads(stdout)
            return json.dumps({
                "ok": True,
                "exit_code": proc.returncode,
                "stdout": parsed,
                "workdir": cwd,
            })
        except json.JSONDecodeError:
            pass  # Fall through to raw output

    return json.dumps({
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr.strip() if stderr else "",
        "workdir": cwd,
    })

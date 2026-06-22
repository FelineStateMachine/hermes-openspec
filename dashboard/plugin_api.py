"""OpenSpec dashboard plugin — backend API routes.

Mounted at /api/plugins/openspec/ by the dashboard plugin system
(``hermes_cli.web_server._mount_plugin_api_routes`` imports this file and
``app.include_router``\\ s it). Every handler is a thin wrapper around the
plugin-local registry (``plugins.openspec.registry``) plus filesystem/git
scanners that live in this module — no core ``web_server`` helpers are used,
so the plugin is self-contained.

Routes
------
- GET    /sources                              — list registered sources (with live board scan)
- POST   /sources                              — register a source by path
- DELETE /sources/{source_id}                  — unregister a source
- PUT    /sources/{source_id}                  — update a source's path/name
- GET    /sources/{source_id}/changes/{change} — change detail (proposal/tasks/design/specs)
- GET    /sources/{source_id}/ideas/{idea}     — idea detail (markdown content)
- GET    /sources/{source_id}/specs?path=      — spec detail (current worktree content)
- GET    /sources/{source_id}/spec-browser     — current/dirty/ref-diff spec browser

Auth
----
HTTP routes go through the dashboard's session-token auth middleware
(``web_server.auth_middleware``) just like core API routes — every
``/api/plugins/...`` request must present the session bearer token (or the
session cookie set when you load the dashboard HTML).
"""

from __future__ import annotations

import difflib
import importlib.util
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Registry import — path-based, because the dashboard plugin loader imports
# this file standalone via importlib (no package context for relative imports).
# ---------------------------------------------------------------------------
_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "registry.py"


def _load_registry():
    if not _REGISTRY_PATH.is_file():
        return None
    spec = importlib.util.spec_from_file_location("openspec_registry", _REGISTRY_PATH)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_registry = _load_registry()

router = APIRouter()


# ---------------------------------------------------------------------------
# Path guards — local equivalents of web_server._fs_path / _fs_find_git_root.
# Kept here so the plugin has zero core-dependency for filesystem traversal.
# ---------------------------------------------------------------------------

def _find_openspec_bin() -> Optional[str]:
    """Locate the ``openspec`` CLI binary."""
    candidates = [
        os.getenv("OPENSPEC_BIN", "").strip(),
        shutil.which("openspec") or "",
        str(Path.home() / ".npm-global" / "bin" / "openspec"),
    ]
    for c in candidates:
        if c and Path(c).exists() and os.access(c, os.X_OK):
            return c
    return None


def _resolve_path(raw_path: str) -> Path:
    """Resolve a user-supplied path string to an absolute Path, rejecting
    null bytes and unparseable values. Mirrors web_server._fs_path semantics."""
    raw = str(raw_path or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Path is required")
    if "\0" in raw:
        raise HTTPException(status_code=400, detail="Invalid path")
    try:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        return candidate.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid path")


def _find_git_root(start: Path) -> Optional[Path]:
    directory = start
    for _ in range(50):
        try:
            if (directory / ".git").exists():
                return directory
        except OSError:
            return None
        parent = directory.parent
        if parent == directory:
            return None
        directory = parent
    return None


def _repo_root(raw_path: str) -> tuple[Path | None, str | None]:
    """Resolve a raw path to a repo root (git root or the path itself).

    Unlike ``_source_root``, this does NOT require ``openspec/`` to exist —
    it's used for add/update so sources can be registered before init.
    """
    try:
        target = _resolve_path(raw_path)
    except HTTPException as exc:
        return None, str(exc.detail)
    if not target.exists():
        return None, "Path does not exist"
    git_root = _find_git_root(target)
    if git_root:
        return git_root, None
    return target, None


def _source_root(raw_path: str) -> tuple[Path | None, str | None]:
    """Resolve a raw path to a repo root containing ``openspec/``.

    Accepts either a repo root, the ``openspec/`` dir itself, or any path
    inside a repo whose root has ``openspec/``.
    """
    try:
        target = _resolve_path(raw_path)
    except HTTPException as exc:
        return None, str(exc.detail)
    openspec_root = target if target.name == "openspec" else target / "openspec"
    if openspec_root.is_dir():
        return openspec_root.parent, None
    git_root = _find_git_root(target)
    if git_root and (git_root / "openspec").is_dir():
        return git_root, None
    return None, "No openspec/ directory found"


# ---------------------------------------------------------------------------
# Markdown / task parsing helpers
# ---------------------------------------------------------------------------

_OPENSPEC_DOC_MAX_BYTES = 512 * 1024
_TASK_DONE_RE = re.compile(r"^- \[[xX]\]", re.MULTILINE)
_TASK_TODO_RE = re.compile(r"^- \[ \]", re.MULTILINE)
_STATUSES = ("ideas", "draft", "todo", "in_progress", "done", "archived")


def _task_stats(tasks_path: Path) -> Optional[dict[str, int]]:
    try:
        content = tasks_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    done = len(_TASK_DONE_RE.findall(content))
    todo = len(_TASK_TODO_RE.findall(content))
    return {"total": done + todo, "done": done}


def _status(has_tasks: bool, stats: Optional[dict[str, int]], *, archived: bool) -> str:
    if archived:
        return "archived"
    if not has_tasks or stats is None:
        return "draft"
    if stats["done"] == 0:
        return "todo"
    if stats["total"] > 0 and stats["done"] == stats["total"]:
        return "done"
    return "in_progress"


def _title_from_markdown(path: Path, fallback: str) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip() or fallback
    except OSError:
        pass
    return fallback


def _read_doc(path: Path) -> Optional[str]:
    try:
        if not path.is_file():
            return None
        if path.stat().st_size > _OPENSPEC_DOC_MAX_BYTES:
            return path.read_text(encoding="utf-8", errors="replace")[:_OPENSPEC_DOC_MAX_BYTES]
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _change_token(name: str) -> str:
    if _registry is not None:
        return _registry.change_token(name)
    return ""


# ---------------------------------------------------------------------------
# Board scan
# ---------------------------------------------------------------------------

def _change_summary(path: Path, source_id: str, *, archived: bool = False) -> Optional[dict[str, Any]]:
    if not path.is_dir():
        return None
    proposal_path = path / "proposal.md"
    tasks_path = path / "tasks.md"
    design_path = path / "design.md"
    specs_path = path / "specs"
    if not proposal_path.is_file():
        return None
    has_tasks = tasks_path.is_file()
    stats = _task_stats(tasks_path) if has_tasks else None
    name = path.name
    return {
        "id": f"{source_id}/{name}",
        "token": _change_token(name),
        "name": name,
        "title": _title_from_markdown(proposal_path, name),
        "status": _status(has_tasks, stats, archived=archived),
        "hasProposal": True,
        "hasTasks": has_tasks,
        "hasDesign": design_path.is_file(),
        "hasSpecs": specs_path.is_dir(),
        "taskStats": stats,
    }


def _idea_summary(path: Path, source_id: str) -> Optional[dict[str, Any]]:
    if not path.is_file() or path.suffix.lower() != ".md":
        return None
    return {
        "id": f"{source_id}/{path.stem}",
        "token": _change_token(path.stem),
        "name": path.stem,
        "title": _title_from_markdown(path, path.stem),
        "status": "ideas",
    }


def _scan(root: Path) -> Optional[dict[str, Any]]:
    openspec_root = root / "openspec"
    if not openspec_root.is_dir():
        return None
    source_id = root.name
    changes: list[dict[str, Any]] = []
    ideas: list[dict[str, Any]] = []
    specs: list[dict[str, Any]] = []

    changes_root = openspec_root / "changes"
    if changes_root.is_dir():
        try:
            for child in sorted(changes_root.iterdir(), key=lambda item: item.name.lower()):
                if child.name == "archive":
                    continue
                change = _change_summary(child, source_id)
                if change is not None:
                    changes.append(change)
        except OSError:
            pass
        archive_root = changes_root / "archive"
        if archive_root.is_dir():
            try:
                for child in sorted(archive_root.iterdir(), key=lambda item: item.name.lower()):
                    change = _change_summary(child, source_id, archived=True)
                    if change is not None:
                        changes.append(change)
            except OSError:
                pass

    ideas_root = openspec_root / "ideas"
    if ideas_root.is_dir():
        try:
            for child in sorted(ideas_root.iterdir(), key=lambda item: item.name.lower()):
                idea = _idea_summary(child, source_id)
                if idea is not None:
                    ideas.append(idea)
        except OSError:
            pass

    specs_root = openspec_root / "specs"
    if specs_root.is_dir():
        try:
            for child in sorted(specs_root.rglob("*.md")):
                rel = child.relative_to(specs_root).as_posix()
                specs.append({
                    "id": f"{source_id}/spec/{rel}",
                    "token": _change_token(f"spec:{rel}"),
                    "name": rel,
                    "path": rel,
                    "title": _title_from_markdown(child, rel),
                })
        except OSError:
            pass

    by_status = {s: 0 for s in _STATUSES}
    by_status["ideas"] = len(ideas)
    for change in changes:
        status = str(change.get("status") or "draft")
        by_status[status] = by_status.get(status, 0) + 1

    return {
        "path": str(openspec_root),
        "changes": changes,
        "ideas": ideas,
        "specs": specs,
        "counts": {
            "changes": len(changes),
            "ideas": len(ideas),
            "specs": len(specs),
            "byStatus": by_status,
        },
    }


def _source_payload(source: dict[str, Any]) -> dict[str, Any]:
    root, error = _repo_root(source["path"])
    name = source.get("name") or (root.name if root else Path(source["path"]).expanduser().name)
    base = {
        "token": source.get("token") or source.get("id"),
        "id": source.get("id") or source.get("token"),
        "name": name,
        "path": str(Path(source["path"]).expanduser()),
    }
    if root is None:
        return {**base, "valid": False, "repoRoot": None, "openspec": None, "error": error}
    # Repo exists — check if openspec/ is initialized.
    if not (root / "openspec").is_dir():
        return {**base, "valid": False, "repoRoot": str(root), "openspec": None, "error": "No openspec/ directory found"}
    return {
        **base,
        "valid": True,
        "repoRoot": str(root),
        "openspec": _scan(root),
        "error": None,
    }


# ---------------------------------------------------------------------------
# Detail helpers
# ---------------------------------------------------------------------------

def _find_change_dir(root: Path, change_name: str) -> tuple[Path | None, bool]:
    changes_root = root / "openspec" / "changes"
    candidate = changes_root / change_name
    if candidate.is_dir():
        return candidate, False
    archive_root = changes_root / "archive"
    if archive_root.is_dir():
        archived = archive_root / change_name
        if archived.is_dir():
            return archived, True
        try:
            for child in archive_root.iterdir():
                if child.is_dir() and (child.name == change_name or child.name.endswith(change_name)):
                    return child, True
        except OSError:
            pass
    return None, False


def _change_detail(root: Path, change_name: str) -> Optional[dict[str, Any]]:
    change_dir, archived = _find_change_dir(root, change_name)
    if change_dir is None:
        return None
    proposal_path = change_dir / "proposal.md"
    tasks_path = change_dir / "tasks.md"
    design_path = change_dir / "design.md"
    specs_root = change_dir / "specs"
    has_tasks = tasks_path.is_file()
    stats = _task_stats(tasks_path) if has_tasks else None
    specs: list[dict[str, Any]] = []
    if specs_root.is_dir():
        try:
            for child in sorted(specs_root.rglob("*.md")):
                rel = child.relative_to(specs_root).as_posix()
                after = _read_doc(child) or ""
                before = _read_worktree_spec(root, rel)
                status = _spec_status(before, after)
                specs.append({
                    "path": rel,
                    "content": after,
                    "before": before,
                    "status": status,
                    "diff": _spec_diff(before, after, rel) if status not in ("unchanged", "missing") else "",
                })
        except OSError:
            pass
    return {
        "name": change_dir.name,
        "title": _title_from_markdown(proposal_path, change_dir.name),
        "status": _status(has_tasks, stats, archived=archived),
        "archived": archived,
        "taskStats": stats,
        "proposal": _read_doc(proposal_path),
        "design": _read_doc(design_path),
        "tasks": _read_doc(tasks_path),
        "specs": specs,
    }


def _idea_detail(root: Path, idea_name: str) -> Optional[dict[str, Any]]:
    ideas_root = root / "openspec" / "ideas"
    candidate = ideas_root / f"{idea_name}.md"
    if not candidate.is_file():
        return None
    return {
        "name": idea_name,
        "title": _title_from_markdown(candidate, idea_name),
        "status": "ideas",
        "content": _read_doc(candidate) or "",
    }


def _spec_detail(root: Path, spec_path: str) -> Optional[dict[str, Any]]:
    specs_root = (root / "openspec" / "specs").resolve()
    candidate = (specs_root / spec_path).resolve()
    if specs_root not in candidate.parents and candidate != specs_root:
        return None
    if not candidate.is_file():
        return None
    return {
        "path": spec_path,
        "title": _title_from_markdown(candidate, spec_path),
        "content": _read_doc(candidate) or "",
    }


# ---------------------------------------------------------------------------
# Spec browser (current / dirty / ref-diff)
# ---------------------------------------------------------------------------

def _git_run(root: Path, args: list[str], *, timeout: int = 8) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _git_output(root: Path, args: list[str], *, timeout: int = 8) -> Optional[str]:
    try:
        proc = _git_run(root, args, timeout=timeout)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _current_branch(root: Path) -> str:
    return (_git_output(root, ["branch", "--show-current"], timeout=3) or "").strip()


def _list_worktree_specs(root: Path) -> list[str]:
    specs_root = root / "openspec" / "specs"
    if not specs_root.is_dir():
        return []
    out: list[str] = []
    try:
        for child in sorted(specs_root.rglob("*.md")):
            out.append(child.relative_to(specs_root).as_posix())
    except OSError:
        return []
    return out


def _list_ref_specs(root: Path, ref: str) -> list[str]:
    ref = (ref or "").strip()
    if not ref:
        return []
    # `git ls-tree` returns paths relative to repo root. No shell involved, so
    # arbitrary refs like origin/main, HEAD~3, or full SHAs are safe arguments.
    text = _git_output(root, ["ls-tree", "-r", "--name-only", ref, "--", "openspec/specs"], timeout=8)
    if text is None:
        return []
    prefix = "openspec/specs/"
    return sorted(
        line[len(prefix):]
        for line in text.splitlines()
        if line.startswith(prefix) and line.endswith(".md")
    )


def _read_worktree_spec(root: Path, spec_path: str) -> Optional[str]:
    specs_root = (root / "openspec" / "specs").resolve()
    candidate = (specs_root / spec_path).resolve()
    if specs_root not in candidate.parents and candidate != specs_root:
        return None
    if not candidate.is_file():
        return None
    return _read_doc(candidate) or ""


def _worktree_spec_mtime(root: Path, spec_path: str) -> Optional[str]:
    """Return ISO-8601 mtime for a worktree spec file, or None if unavailable."""
    specs_root = (root / "openspec" / "specs").resolve()
    candidate = (specs_root / spec_path).resolve()
    if specs_root not in candidate.parents and candidate != specs_root:
        return None
    try:
        return datetime.fromtimestamp(candidate.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return None


def _spec_git_dates(root: Path) -> dict[str, dict[str, str]]:
    """Return ``{rel_path: {"mtime": iso, "ctime": iso}}`` for each spec.

    Uses a single ``git log`` call (newest-first). The first time a file
    appears is its most recent commit (mtime); the last time is the oldest
    commit (ctime / creation date). Falls back to an empty dict if git is
    unavailable.
    """
    text = _git_output(
        root,
        ["log", "--no-merges", "--format=%cI", "--name-only", "--", "openspec/specs/"],
        timeout=10,
    )
    if not text:
        return {}
    prefix = "openspec/specs/"
    dates: dict[str, dict[str, str]] = {}
    current_date: Optional[str] = None
    for line in text.splitlines():
        if not line:
            continue
        if line.startswith(prefix):
            rel = line[len(prefix):]
            if not rel.endswith(".md") or not current_date:
                continue
            if rel not in dates:
                dates[rel] = {"mtime": current_date, "ctime": current_date}
            else:
                dates[rel]["ctime"] = current_date
        else:
            current_date = line.strip()
    return dates


def _read_ref_spec(root: Path, ref: str, spec_path: str) -> Optional[str]:
    ref = (ref or "").strip()
    if not ref:
        return None
    if spec_path.startswith("/") or ".." in Path(spec_path).parts:
        return None
    return _git_output(root, ["show", f"{ref}:openspec/specs/{spec_path}"], timeout=8)


def _spec_title_from_content(content: Optional[str], fallback: str) -> str:
    for line in (content or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback


def _spec_diff(before: Optional[str], after: Optional[str], path: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            (before or "").splitlines(),
            (after or "").splitlines(),
            fromfile=f"before/{path}",
            tofile=f"after/{path}",
            lineterm="",
        )
    )


def _spec_status(before: Optional[str], after: Optional[str]) -> str:
    if before is None and after is None:
        return "missing"
    if before is None:
        return "added"
    if after is None:
        return "deleted"
    if before != after:
        return "modified"
    return "unchanged"


def _spec_browser(root: Path, before: str = "", after: str = "", dirty: bool = False) -> dict[str, Any]:
    before_ref = (before or "").strip()
    after_ref = (after or "").strip()
    dirty_mode = bool(dirty)

    if dirty_mode:
        before_ref = before_ref or "HEAD"
        after_label = "working tree"
        before_paths = _list_ref_specs(root, before_ref)
        after_paths = _list_worktree_specs(root)
        mode = "dirty"
    elif before_ref or after_ref:
        if not before_ref or not after_ref:
            raise HTTPException(status_code=400, detail="both before and after are required for ref diff")
        after_label = after_ref
        before_paths = _list_ref_specs(root, before_ref)
        after_paths = _list_ref_specs(root, after_ref)
        mode = "refs"
    else:
        after_label = "working tree"
        before_paths = []
        after_paths = _list_worktree_specs(root)
        mode = "current"

    files: list[dict[str, Any]] = []
    # Pre-fetch git commit dates for all specs in one call (current/dirty modes).
    git_dates = _spec_git_dates(root) if mode in ("current", "dirty") else {}
    for rel in sorted(set(before_paths) | set(after_paths)):
        if mode == "current":
            # No comparison — just showing the current worktree state.
            after_content = _read_worktree_spec(root, rel)
            gd = git_dates.get(rel, {})
            files.append({
                "path": rel,
                "token": _change_token(f"spec:{rel}"),
                "title": _spec_title_from_content(after_content, rel),
                "status": "current" if after_content is not None else "missing",
                "changed": False,
                "mtime": gd.get("mtime") or _worktree_spec_mtime(root, rel),
                "ctime": gd.get("ctime"),
                "before": None,
                "after": after_content,
                "diff": "",
            })
            continue
        before_content = _read_ref_spec(root, before_ref, rel) if before_ref else None
        if dirty_mode:
            after_content = _read_worktree_spec(root, rel)
            gd = git_dates.get(rel, {})
            mtime = gd.get("mtime") or _worktree_spec_mtime(root, rel)
            ctime = gd.get("ctime")
        else:
            after_content = _read_ref_spec(root, after_ref, rel)
            mtime = None
            ctime = None
        status = _spec_status(before_content, after_content)
        # In dirty mode, skip unchanged specs — only show what's actually
        # different between HEAD and the worktree.
        if dirty_mode and status in ("unchanged", "missing"):
            continue
        files.append({
            "path": rel,
            "token": _change_token(f"spec:{rel}"),
            "title": _spec_title_from_content(after_content if after_content is not None else before_content, rel),
            "status": status,
            "changed": status not in {"unchanged", "missing"},
            "mtime": mtime,
            "ctime": ctime,
            "before": before_content,
            "after": after_content,
            "diff": _spec_diff(before_content, after_content, rel) if status not in {"unchanged", "missing"} else "",
        })

    return {
        "mode": mode,
        "branch": _current_branch(root),
        "before": before_ref or None,
        "after": after_label,
        "files": files,
        "changedCount": sum(1 for item in files if item["changed"]),
    }


# ---------------------------------------------------------------------------
# Source resolution
# ---------------------------------------------------------------------------

class _SourceCreate(BaseModel):
    path: str
    name: Optional[str] = None


def _resolve_source(source_id: str) -> tuple[dict[str, Any], Path]:
    if _registry is None:
        raise HTTPException(status_code=503, detail="OpenSpec registry not available")
    source = _registry.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    root, error = _source_root(source["path"])
    if root is None:
        raise HTTPException(status_code=400, detail=error or "Source is invalid")
    return source, root


# ---------------------------------------------------------------------------
# Legacy config migration (one-time, idempotent)
# ---------------------------------------------------------------------------

_migration_done = False


def _registered_sources() -> list[dict[str, Any]]:
    global _migration_done
    if _registry is None:
        return []
    if not _migration_done:
        _migration_done = True
        try:
            from hermes_cli.config import load_config
            dashboard = (load_config() or {}).get("dashboard") or {}
            legacy = dashboard.get("openspec_sources")
            if isinstance(legacy, list) and legacy:
                _registry.migrate_from_config_sources(legacy)
        except Exception:
            pass
    return _registry.list_sources()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/sources")
def list_sources():
    return {"sources": [_source_payload(s) for s in _registered_sources()]}


@router.post("/sources")
def add_source(body: _SourceCreate):
    if _registry is None:
        raise HTTPException(status_code=503, detail="OpenSpec registry not available")
    raw_path = str(body.path or "").strip()
    if not raw_path:
        raise HTTPException(status_code=400, detail="path is required")
    root, error = _repo_root(raw_path)
    if root is None:
        raise HTTPException(status_code=400, detail=error or "Invalid path")
    try:
        source = _registry.add_source(raw_path, str(body.name or "").strip())
    except ValueError:
        raise HTTPException(status_code=409, detail="Source already registered")
    return {"ok": True, "source": _source_payload(source)}


@router.delete("/sources/{source_id}")
def remove_source(source_id: str):
    if _registry is None:
        raise HTTPException(status_code=503, detail="OpenSpec registry not available")
    if not _registry.remove_source(source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    return {"ok": True}


@router.put("/sources/{source_id}")
def update_source(source_id: str, body: _SourceCreate):
    if _registry is None:
        raise HTTPException(status_code=503, detail="OpenSpec registry not available")
    raw_path = str(body.path or "").strip()
    if not raw_path:
        raise HTTPException(status_code=400, detail="path is required")
    root, error = _repo_root(raw_path)
    if root is None:
        raise HTTPException(status_code=400, detail=error or "Invalid path")
    try:
        source = _registry.update_source(source_id, path=raw_path, name=str(body.name or "").strip())
    except ValueError:
        raise HTTPException(status_code=409, detail="Source already registered")
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"ok": True, "source": _source_payload(source)}


@router.post("/sources/{source_id}/init")
def init_source(source_id: str):
    if _registry is None:
        raise HTTPException(status_code=503, detail="OpenSpec registry not available")
    source = _registry.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    root, error = _repo_root(source["path"])
    if root is None:
        raise HTTPException(status_code=400, detail=error or "Invalid path")
    if (root / "openspec").is_dir():
        return {"ok": True, "message": "Already initialized", "source": _source_payload(source)}
    # Try `openspec init <path> --tools none` first.
    exe = _find_openspec_bin()
    if exe:
        try:
            proc = subprocess.run(
                [exe, "init", str(root), "--tools", "none"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout or "").strip()
                raise HTTPException(status_code=500, detail=f"openspec init failed: {detail}")
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="openspec init timed out")
    else:
        # Fallback: create the minimal directory structure.
        try:
            (root / "openspec" / "changes").mkdir(parents=True, exist_ok=True)
            (root / "openspec" / "specs").mkdir(parents=True, exist_ok=True)
            (root / "openspec" / "ideas").mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to create openspec/ structure: {exc}")
    return {"ok": True, "message": "OpenSpec initialized", "source": _source_payload(source)}


@router.get("/sources/{source_id}/changes/{change_name}")
def change_detail(source_id: str, change_name: str):
    _source, root = _resolve_source(source_id)
    detail = _change_detail(root, change_name)
    if detail is None:
        raise HTTPException(status_code=404, detail="Change not found")
    return detail


@router.get("/sources/{source_id}/ideas/{idea_name}")
def idea_detail(source_id: str, idea_name: str):
    _source, root = _resolve_source(source_id)
    detail = _idea_detail(root, idea_name)
    if detail is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return detail


@router.get("/sources/{source_id}/spec-browser")
def spec_browser(
    source_id: str,
    before: str = "",
    after: str = "",
    dirty: bool = False,
):
    _source, root = _resolve_source(source_id)
    return _spec_browser(root, before=before, after=after, dirty=dirty)


@router.get("/sources/{source_id}/specs")
def spec_detail(source_id: str, path: str = Query(...)):
    _source, root = _resolve_source(source_id)
    detail = _spec_detail(root, path)
    if detail is None:
        raise HTTPException(status_code=404, detail="Spec not found")
    return detail

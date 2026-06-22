"""OpenSpec CLI-backed Hermes tool handlers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


MAX_OUTPUT_CHARS = 50_000


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
    artifact = str(args.get("artifact") or "").strip()
    if artifact:
        cmd.append(artifact)
    change = str(args.get("change") or "").strip()
    if change:
        cmd.extend(["--change", change])
    schema = str(args.get("schema") or "").strip()
    if schema:
        cmd.extend(["--schema", schema])
    return _run(cmd, args.get("workdir"))

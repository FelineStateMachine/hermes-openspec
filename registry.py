"""SQLite-backed registry of OpenSpec sources (repos with an ``openspec/`` dir).

Each registered source keeps a stable internal token, but the user-facing copy
format is the source's vanity name (for example ``puzzletea``) plus a derived
change token (for example ``puzzletea/os_a1b2c3``). The OpenSpec plugin's
``openspec_context`` tool resolves the vanity name back to the repo path and
maps the change token to the matching change folder.

The DB lives at ``<hermes_home>/openspec.db`` and is shared between the dashboard
plugin (which owns source CRUD via its ``plugin_api.py`` routes) and the agent
plugin (which only reads to resolve sources). Schema is intentionally tiny —
one row per source. Change contents are not stored; changes are addressed live
by deterministic tokens derived from their folder names. The only per-change
metadata kept here is dashboard-local sequence order, assigned when the
dashboard first observes a change so OpenSpec files remain untouched.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

from hermes_constants import get_hermes_home

_TOKEN_PREFIX = "os_"
_TOKEN_NBYTES = 3  # 6 hex chars
_CHANGE_TOKEN_HEXLEN = 6  # os_ + 6 hex chars, derived from the change name


def db_path() -> Path:
    """Absolute path to the OpenSpec registry DB for the active Hermes home."""
    return get_hermes_home() / "openspec.db"


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS openspec_sources (
            token       TEXT PRIMARY KEY,
            name        TEXT NOT NULL DEFAULT '',
            path        TEXT NOT NULL,
            created_at  REAL NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_openspec_sources_path ON openspec_sources(path)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS change_sequence (
            source_id     TEXT NOT NULL,
            change_name   TEXT NOT NULL,
            group_id      TEXT NOT NULL DEFAULT 'default',
            position      INTEGER NOT NULL,
            depends_on    TEXT NOT NULL DEFAULT '[]',
            first_seen_at REAL NOT NULL,
            updated_at    REAL NOT NULL,
            PRIMARY KEY (source_id, change_name)
        )
        """
    )
    _ensure_change_sequence_columns(conn)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_change_sequence_source_position ON change_sequence(source_id, position)"
    )
    return conn


def _ensure_change_sequence_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(change_sequence)").fetchall()}
    if "group_id" not in cols:
        conn.execute("ALTER TABLE change_sequence ADD COLUMN group_id TEXT NOT NULL DEFAULT 'default'")
    if "depends_on" not in cols:
        conn.execute("ALTER TABLE change_sequence ADD COLUMN depends_on TEXT NOT NULL DEFAULT '[]'")


def _sequence_row(row: sqlite3.Row) -> dict[str, Any]:
    try:
        depends_on = json.loads(row["depends_on"] or "[]")
    except Exception:
        depends_on = []
    if not isinstance(depends_on, list):
        depends_on = []
    return {
        "groupId": row["group_id"] or "default",
        "position": int(row["position"]),
        "dependsOn": [str(item) for item in depends_on],
        "firstSeenAt": row["first_seen_at"],
        "updatedAt": row["updated_at"],
    }


def _gen_token(conn: sqlite3.Connection) -> str:
    for _ in range(64):
        token = _TOKEN_PREFIX + secrets.token_hex(_TOKEN_NBYTES)
        exists = conn.execute(
            "SELECT 1 FROM openspec_sources WHERE token = ?", (token,)
        ).fetchone()
        if not exists:
            return token
    # Astronomically unlikely; widen the space rather than fail.
    return _TOKEN_PREFIX + secrets.token_hex(_TOKEN_NBYTES + 2)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "token": row["token"],
        "id": row["token"],  # back-compat alias for existing dashboard code
        "name": row["name"] or "",
        "path": row["path"],
        "created_at": row["created_at"],
    }


def list_sources() -> list[dict[str, Any]]:
    """All registered sources, oldest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM openspec_sources ORDER BY created_at ASC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_source(token: str) -> Optional[dict[str, Any]]:
    token = (token or "").strip()
    if not token:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM openspec_sources WHERE token = ?", (token,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def effective_name(source: dict[str, Any]) -> str:
    """The human-facing vanity name for a source: stored name or path basename."""
    return (source.get("name") or "").strip() or Path(source["path"]).expanduser().name


def get_source_by_name(name: str) -> Optional[dict[str, Any]]:
    """Look up a source by its vanity name (case-insensitive). First match wins.

    Matches against ``effective_name`` so a source registered without an explicit
    display name still resolves by its path basename.
    """
    key = (name or "").strip().lower()
    if not key:
        return None
    for source in list_sources():
        if effective_name(source).lower() == key:
            return source
    return None


def change_token(change_name: str) -> str:
    """Deterministic, opaque token for a change, derived from its folder name.

    Stable across restarts and never stored — the resolver recomputes it for each
    change on disk and matches, so the DB can never drift from the filesystem.
    """
    digest = hashlib.sha256((change_name or "").encode("utf-8")).hexdigest()
    return _TOKEN_PREFIX + digest[:_CHANGE_TOKEN_HEXLEN]


def get_source_by_path(path: str) -> Optional[dict[str, Any]]:
    normalized = str(Path(path).expanduser())
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM openspec_sources WHERE path = ?", (normalized,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def add_source(path: str, name: str = "") -> dict[str, Any]:
    """Register a source. Raises ValueError if the path is already registered."""
    normalized = str(Path(path).expanduser())
    with _connect() as conn:
        existing = conn.execute(
            "SELECT * FROM openspec_sources WHERE path = ?", (normalized,)
        ).fetchone()
        if existing:
            raise ValueError("Source already registered")
        token = _gen_token(conn)
        conn.execute(
            "INSERT INTO openspec_sources (token, name, path, created_at) VALUES (?, ?, ?, ?)",
            (token, (name or "").strip(), normalized, time.time()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM openspec_sources WHERE token = ?", (token,)
        ).fetchone()
    return _row_to_dict(row)


def update_source(token: str, *, path: str, name: str = "") -> Optional[dict[str, Any]]:
    """Update a registered source. Raises ValueError if the new path conflicts."""
    token = (token or "").strip()
    normalized = str(Path(path).expanduser())
    if not token or not normalized:
        return None
    with _connect() as conn:
        current = conn.execute(
            "SELECT * FROM openspec_sources WHERE token = ?", (token,)
        ).fetchone()
        if current is None:
            return None
        conflict = conn.execute(
            "SELECT token FROM openspec_sources WHERE path = ? AND token != ?",
            (normalized, token),
        ).fetchone()
        if conflict:
            raise ValueError("Source already registered")
        conn.execute(
            "UPDATE openspec_sources SET name = ?, path = ? WHERE token = ?",
            ((name or "").strip(), normalized, token),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM openspec_sources WHERE token = ?", (token,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def remove_source(token: str) -> bool:
    token = (token or "").strip()
    if not token:
        return False
    with _connect() as conn:
        cur = conn.execute("DELETE FROM openspec_sources WHERE token = ?", (token,))
        conn.execute("DELETE FROM change_sequence WHERE source_id = ?", (token,))
        conn.commit()
        return cur.rowcount > 0


def ensure_change_sequence(source_id: str, change_names: list[str]) -> dict[str, dict[str, Any]]:
    """Ensure dashboard-local sequence rows exist for observed changes.

    Existing positions are preserved. Newly observed change folders append after
    the current max position in the order provided by the scanner. This keeps
    sequencing out of OpenSpec files and avoids parsing naming conventions.
    """
    source_id = (source_id or "").strip()
    names: list[str] = []
    seen: set[str] = set()
    for raw in change_names or []:
        name = str(raw or "").strip()
        if name and name not in seen:
            names.append(name)
            seen.add(name)
    if not source_id or not names:
        return {}

    now = time.time()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT change_name, group_id, position, depends_on, first_seen_at, updated_at FROM change_sequence WHERE source_id = ?",
            (source_id,),
        ).fetchall()
        existing = {r["change_name"]: r for r in rows}
        max_pos = max((int(r["position"]) for r in rows), default=0)
        for name in names:
            if name in existing:
                continue
            max_pos += 1
            conn.execute(
                "INSERT INTO change_sequence (source_id, change_name, position, first_seen_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (source_id, name, max_pos, now, now),
            )
        conn.commit()
        rows = conn.execute(
            "SELECT change_name, group_id, position, depends_on, first_seen_at, updated_at FROM change_sequence WHERE source_id = ?",
            (source_id,),
        ).fetchall()

    wanted = set(names)
    return {
        r["change_name"]: _sequence_row(r)
        for r in rows
        if r["change_name"] in wanted
    }


def get_change_sequence(source_id: str, change_names: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """Return dashboard-local sequence metadata for a source."""
    source_id = (source_id or "").strip()
    if not source_id:
        return {}
    names = {str(name or "").strip() for name in (change_names or []) if str(name or "").strip()}
    with _connect() as conn:
        rows = conn.execute(
            "SELECT change_name, group_id, position, depends_on, first_seen_at, updated_at FROM change_sequence WHERE source_id = ? ORDER BY position ASC, change_name ASC",
            (source_id,),
        ).fetchall()
    return {
        r["change_name"]: _sequence_row(r)
        for r in rows
        if not names or r["change_name"] in names
    }


def set_change_sequence(
    source_id: str,
    change_names: list[str],
    *,
    group_id: str = "default",
    dependencies: dict[str, list[str]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Explicitly set agent-declared order/dependencies for a set of changes."""
    source_id = (source_id or "").strip()
    group_id = (group_id or "default").strip() or "default"
    names: list[str] = []
    seen: set[str] = set()
    for raw in change_names or []:
        name = str(raw or "").strip()
        if name and name not in seen:
            names.append(name)
            seen.add(name)
    if not source_id or not names:
        return {}
    deps = dependencies or {}
    now = time.time()
    with _connect() as conn:
        existing_rows = conn.execute(
            "SELECT change_name, first_seen_at FROM change_sequence WHERE source_id = ?",
            (source_id,),
        ).fetchall()
        first_seen = {r["change_name"]: r["first_seen_at"] for r in existing_rows}
        for index, name in enumerate(names, start=1):
            depends_on = [str(item).strip() for item in deps.get(name, []) if str(item).strip()]
            conn.execute(
                """
                INSERT INTO change_sequence (source_id, change_name, group_id, position, depends_on, first_seen_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, change_name) DO UPDATE SET
                    group_id = excluded.group_id,
                    position = excluded.position,
                    depends_on = excluded.depends_on,
                    updated_at = excluded.updated_at
                """,
                (source_id, name, group_id, index, json.dumps(depends_on), first_seen.get(name, now), now),
            )
        conn.commit()
    return get_change_sequence(source_id, names)


def parse_identifier(identifier: str) -> tuple[str, Optional[str]]:
    """Split a pasted identifier into ``(source, change_token | None)``.

    Accepts a vanity name (``puzzletea``) or ``puzzletea/os_a1b2c3``. The first
    segment locates the source (by vanity name, or legacy ``os_`` source token);
    everything after the first ``/`` is the change token. The resolver maps the
    change token back to a change folder by recomputing ``change_token`` for each
    change on disk, so nothing about changes is ever stored.
    """
    raw = (identifier or "").strip()
    if "/" in raw:
        source, _, change = raw.partition("/")
        return source.strip(), (change.strip() or None)
    return raw, None


def migrate_from_config_sources(config_sources: list[dict[str, Any]]) -> int:
    """One-time import of legacy ``config.yaml`` ``dashboard.openspec_sources``.

    Returns the number of rows inserted. Idempotent: paths already present are
    skipped, so calling it repeatedly is safe.
    """
    inserted = 0
    for item in config_sources or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        try:
            add_source(path, str(item.get("name") or "").strip())
            inserted += 1
        except ValueError:
            continue  # already migrated
    return inserted

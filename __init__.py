"""OpenSpec plugin — registers CLI-backed spec workflow tools."""

from __future__ import annotations

try:
    from . import schemas
    from . import tools
except ImportError:  # pragma: no cover - pytest may import the repo root as a top-level module
    import schemas  # type: ignore
    import tools  # type: ignore

_TOOLS = (
    ("openspec_list", schemas.OPENSPEC_LIST, tools.openspec_list, "📋"),
    ("openspec_show", schemas.OPENSPEC_SHOW, tools.openspec_show, "📖"),
    ("openspec_validate", schemas.OPENSPEC_VALIDATE, tools.openspec_validate, "✅"),
    ("openspec_status", schemas.OPENSPEC_STATUS, tools.openspec_status, "📊"),
    ("openspec_instructions", schemas.OPENSPEC_INSTRUCTIONS, tools.openspec_instructions, "🧭"),
)

_WRITE_TOOLS = (
    ("openspec_idea_create", schemas.OPENSPEC_IDEA_CREATE, tools.openspec_idea_create, "💡"),
    ("openspec_idea_enrich", schemas.OPENSPEC_IDEA_ENRICH, tools.openspec_idea_enrich, "🔎"),
    ("openspec_idea_promote", schemas.OPENSPEC_IDEA_PROMOTE, tools.openspec_idea_promote, "🚀"),
    ("openspec_task_list", schemas.OPENSPEC_TASK_LIST, tools.openspec_task_list, "☑️"),
    ("openspec_task_set_status", schemas.OPENSPEC_TASK_SET_STATUS, tools.openspec_task_set_status, "✅"),
    ("openspec_change_create", schemas.OPENSPEC_CHANGE_CREATE, tools.openspec_change_create, "📝"),
    ("openspec_change_promote", schemas.OPENSPEC_CHANGE_PROMOTE, tools.openspec_change_promote, "➡️"),
    ("openspec_change_archive", schemas.OPENSPEC_CHANGE_ARCHIVE, tools.openspec_change_archive, "📦"),
    ("openspec_change_unarchive", schemas.OPENSPEC_CHANGE_UNARCHIVE, tools.openspec_change_unarchive, "♻️"),
    ("openspec_spec_diff", schemas.OPENSPEC_SPEC_DIFF, tools.openspec_spec_diff, "🔍"),
    ("openspec_spec_create", schemas.OPENSPEC_SPEC_CREATE, tools.openspec_spec_create, "✏️"),
    ("openspec_spec_show", schemas.OPENSPEC_SPEC_SHOW, tools.openspec_spec_show, "📄"),
    ("openspec_spec_list", schemas.OPENSPEC_SPEC_LIST, tools.openspec_spec_list, "📋"),
)


def _check_openspec_available() -> bool:
    return tools._openspec_bin() is not None


def register(ctx) -> None:
    # openspec_context only reads the registry DB + files on disk, so it is
    # available even when the openspec CLI binary is not installed. It is the
    # entry point for resolving copyable 'os_' identifiers.
    ctx.register_tool(
        name="openspec_context",
        toolset="openspec",
        schema=schemas.OPENSPEC_CONTEXT,
        handler=tools.openspec_context,
        emoji="🔖",
    )
    for name, schema, handler, emoji in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset="openspec",
            schema=schema,
            handler=handler,
            check_fn=_check_openspec_available,
            emoji=emoji,
        )
    for name, schema, handler, emoji in _WRITE_TOOLS:
        ctx.register_tool(
            name=name,
            toolset="openspec",
            schema=schema,
            handler=handler,
            emoji=emoji,
        )

"""OpenSpec plugin — registers CLI-backed spec workflow tools."""

from __future__ import annotations

from . import schemas
from . import tools

_TOOLS = (
    ("openspec_list", schemas.OPENSPEC_LIST, tools.openspec_list, "📋"),
    ("openspec_show", schemas.OPENSPEC_SHOW, tools.openspec_show, "📖"),
    ("openspec_validate", schemas.OPENSPEC_VALIDATE, tools.openspec_validate, "✅"),
    ("openspec_status", schemas.OPENSPEC_STATUS, tools.openspec_status, "📊"),
    ("openspec_instructions", schemas.OPENSPEC_INSTRUCTIONS, tools.openspec_instructions, "🧭"),
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

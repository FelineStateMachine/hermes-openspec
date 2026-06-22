## Why

Fresh OpenSpec repositories exposed three maintainer-visible workflow problems:

1. Before initialization, OpenSpec list operations fail with `No OpenSpec changes directory found`; the plugin should make dashboard initialization create a complete, CLI-listable OpenSpec layout.
2. `openspec init --tools none` creates `changes/` and `specs/` but not the plugin-supported `ideas/` directory, and may omit `changes/archive/` in fallback paths; the dashboard should normalize the layout after either CLI init or fallback init.
3. `openspec_instructions` can fail in freshly initialized repositories because the OpenSpec CLI requires an existing change, and the tool description advertised `spec` even though the CLI artifact is `specs`; the agent tool should accept the natural alias and return useful template guidance when no change exists.

## What Changes

- Add layout normalization after dashboard source initialization so initialized sources always contain `openspec/changes/`, `openspec/changes/archive/`, `openspec/specs/`, and `openspec/ideas/`.
- Add fallback behavior to `openspec_instructions` for no-change repositories by returning the package template for the requested artifact.
- Normalize `artifact="spec"` to `artifact="specs"` for the tool and schema description.
- Add regression tests for the initialization layout and fresh-repo instruction fallback.
- Make the plugin package importable under pytest from the repository root so regression tests can run locally.

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `dashboard-sources`: source initialization must normalize all plugin-supported OpenSpec directories.
- `agent-tools`: instructions lookup must tolerate fresh repositories and the `spec` alias.

## Impact

- `dashboard/plugin_api.py`
- `tools.py`
- `schemas.py`
- `__init__.py`
- `tests/test_openspec_workflow_fixes.py`

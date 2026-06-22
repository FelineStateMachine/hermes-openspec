## Why

The frontend `parseSpec` function in `dashboard/dist/index.js` parses OpenSpec spec markdown into structured data (title, purpose, requirements with scenarios). This logic exists only in JavaScript — the Python backend and agent tools can't use it. Meanwhile, the dashboard's spec diff is line-level unified diff (`difflib.unified_diff`), which shows what text changed but not what requirements or scenarios changed. Agents have no way to get a structured delta at all — they must read two full specs and mentally diff them.

## What Changes

Extract the spec parser into a shared Python function, build a semantic diff function on top of it, and expose it as a new `openspec_spec_diff` agent tool. The tool returns a structured JSON delta at the requirement/scenario level (added, modified, removed, unchanged) plus a unified line diff as a fallback field. Filesystem-backed — works without the OpenSpec CLI binary, same as the idea and change lifecycle tools.

## Capabilities

### New Capabilities
- `semantic-spec-diff`: Python spec parser, semantic diff function, and `openspec_spec_diff` agent tool for comparing specs at the requirement/scenario level

### Modified Capabilities
- `agent-tools`: New `openspec_spec_diff` tool added to the plugin's registered tools, filesystem-backed (always available, no CLI gating)

## Impact

- `tools.py` — new `_parse_spec()`, `_semantic_spec_diff()`, and `openspec_spec_diff()` functions
- `schemas.py` — new `OPENSPEC_SPEC_DIFF` schema
- `__init__.py` — register the new tool (filesystem-backed, no `check_fn`)
- `plugin.yaml` — add `openspec_spec_diff` to `provides_tools`
- `tests/` — new test file for parser, diff, and tool handler

## Why

The spec browser uses raw `Markdown` rendering in dirty and refs diff modes — two unstructured markdown blobs side-by-side. This is inconsistent with the change > Specs tab, which uses `SpecContentView` (structured requirement/scenario rendering). The spec list in dirty/refs mode also shows only a `changed` badge with no indication of what changed at the requirement level, so maintainers must click into each spec to see the delta.

## What Changes

Switch the spec browser's dirty and refs modes from raw `Markdown` to `SpecContentView` for before/after rendering. Add a compact semantic summary to spec list items in dirty/refs mode — requirement-level added/modified/removed counts computed from before/after content — so maintainers see "+2 req, ~1, -0" at a glance before clicking in.

## Capabilities

### New Capabilities
- `spec-browser-structured-rendering`: Structured rendering in spec browser diff modes and compact semantic summary in the spec list

### Modified Capabilities
- `spec-browser`: Requirements modified to use structured rendering in diff modes and include semantic summary in list entries

## Impact

- `dashboard/dist/index.js` — `SpecsView` uses `SpecContentView` instead of `Markdown` in dirty/refs modes; spec list items show semantic summary
- `dashboard/plugin_api.py` — `_spec_browser` computes `semantic_summary` (added/modified/removed counts) per spec in dirty and refs modes
- `openspec/specs/spec-browser/spec.md` — delta spec adding structured rendering and semantic summary requirements

### Dependencies

- Requires `semantic-spec-diff-tool` — the shared `_parse_spec` and `_semantic_spec_diff` functions for computing summaries

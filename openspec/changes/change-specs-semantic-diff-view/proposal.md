## Why

The change > Specs tab currently shows side-by-side full specs plus a unified line diff — three views of the same data with no summary of what actually changed at the requirement level. For a change that touches one scenario in a 10-requirement spec, the maintainer has to scan two full documents to find the difference. The semantic delta computed by the shared parser (from the `semantic-spec-diff-tool` change) should drive this view instead.

## What Changes

Replace the "Diff vs current" side-by-side view in `ChangeSpecsView` with a semantic delta view. The backend `_change_detail` function computes a `semantic_diff` field per spec. The frontend renders a summary-first view: requirement-level added/modified/removed sections with scenario-level deltas inside modified requirements, unchanged requirements collapsed by default, and the unified line diff as a collapsible raw fallback at the bottom.

## Capabilities

### New Capabilities
- `change-specs-semantic-diff-view`: Frontend `SpecDeltaView` component and backend `semantic_diff` field in change detail, rendering requirement-level deltas instead of side-by-side full specs

### Modified Capabilities
- `change-board`: The "Delta spec comparison" requirement is modified to include semantic diff alongside the existing unified diff in change detail responses

## Impact

- `dashboard/plugin_api.py` — `_change_detail` computes `semantic_diff` per spec using the shared `_semantic_spec_diff` function
- `dashboard/dist/index.js` — new `SpecDeltaView` component; `ChangeSpecsView` updated to use it for the diff mode
- `dashboard/dist/style.css` — styles for delta sections, added/modified/removed badges, collapsible unchanged requirements
- `openspec/specs/change-board/spec.md` — delta spec modifying the "Delta spec comparison" requirement

### Dependencies

- Requires `semantic-spec-diff-tool` — the shared `_parse_spec` and `_semantic_spec_diff` functions must exist in `tools.py` before the backend can use them

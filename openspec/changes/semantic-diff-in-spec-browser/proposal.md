# Semantic diff in spec browser

## Summary

The change detail's Specs tab renders `SpecDeltaView` — the structured requirement/scenario-level delta from `spec_parser.semantic_spec_diff`. The spec browser (current/dirty/refs modes) only shows side-by-side `SpecContentView` + raw unified diff. The backend already computes `semantic_summary` (the +/~/− counts) for changed files in `_spec_browser()` but discards the full `semantic_diff`. This change wires the full `semantic_diff` into the spec-browser payload and renders `SpecDeltaView` there too, making diffing consistent across both views.

## Motivation

The two spec-diffing surfaces in the dashboard are inconsistent. A user reviewing a change's specs sees a structured, navigable delta (added/modified/removed requirements with scenario-level breakdowns). The same user diffing specs in the browser sees raw text comparison. The backend already has the parsing logic — it's just not being used in the browser path.

## Design

### Backend (`dashboard/plugin_api.py`)

In `_spec_browser()`, for each changed file (status not in unchanged/missing), compute and include the full `semantic_diff` alongside the existing `semantic_summary`. The `_compute_semantic_diff()` helper already exists and is used by `_change_detail()`.

### Frontend (`dashboard/dist/index.js`)

In `SpecsView`, for dirty/refs modes, add a view-mode toggle: **Semantic** (default, `SpecDeltaView`) / **Side-by-side** (existing `SpecContentView` columns) / **Raw** (unified diff only). The `SpecDeltaView` component already exists and handles the semantic diff structure.

"Current" mode stays as-is — no diff, just `SpecContentView`.

### Payload impact

`semantic_diff` adds structured JSON per changed file. For repos with many changed specs this could be large, but it's gated to changed files only (same as the current `semantic_summary` gating).

## Alternatives considered

- **Always use SpecDeltaView, remove side-by-side.** Rejected — side-by-side is useful for reading full spec content side-by-side, which the semantic view doesn't show.
- **Compute semantic_diff client-side from before/after strings.** Rejected — the Python parser already exists and is the single source of truth. Duplicating it in JS risks drift.

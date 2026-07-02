## Context

The dashboard has two spec-diffing surfaces:

1. **Change detail → Specs tab** (`ChangeSpecsView`) — renders `SpecDeltaView`, a structured requirement/scenario-level delta computed by `spec_parser.semantic_spec_diff()`. This is the "proposed vs current" diff for a specific change's delta specs.

2. **Spec browser** (`SpecsView`) — renders side-by-side `SpecContentView` columns + raw unified diff. Used for current/dirty/refs browsing across all specs in a repo.

The backend (`plugin_api.py`) already has the shared `_compute_semantic_diff()` helper, used by `_change_detail()` for surface #1. For surface #2, `_spec_browser()` computes only `semantic_summary` (compact +/~/− counts) for changed files but discards the full `semantic_diff`. The `SpecDeltaView` frontend component already exists and handles the structured delta rendering.

## Goals / Non-Goals

**Goals:**
- Make the spec browser's dirty/refs modes render the same structured semantic delta as the change detail view
- Add a view-mode toggle so users can switch between semantic, side-by-side, and raw diff
- Reuse existing components (`SpecDeltaView`, `SpecContentView`) and backend helpers (`_compute_semantic_diff`)

**Non-Goals:**
- Changing the "current" mode (no comparison — stays as `SpecContentView` only)
- Modifying the change detail's Specs tab (already uses `SpecDeltaView`)
- Adding new parsing logic (the parser is shared in `spec_parser.py`)

## Decisions

### Decision 1: Include full `semantic_diff` in the spec browser payload

**Choice:** Add a `semantic_diff` field to each changed file entry in `_spec_browser()`, computed via the existing `_compute_semantic_diff(before, after)` helper.

**Why not compute client-side:** The Python parser in `spec_parser.py` is the single source of truth. Duplicating it in JS risks drift. The backend already imports and calls it — we're just using the full result instead of discarding it.

**Why not a separate API call:** The before/after content is already loaded in the same payload. Computing the diff server-side is a single function call, no extra I/O.

### Decision 2: View-mode toggle with three modes

**Choice:** Add a toggle in the `SpecsView` toolbar (dirty/refs modes only) with three options: **Semantic** (default), **Side-by-side**, **Raw**.

| Mode | Component | Shows |
|---|---|---|
| Semantic (default) | `SpecDeltaView` | Structured requirement/scenario delta with added/modified/removed sections |
| Side-by-side | Two `SpecContentView` columns | Full before/after spec content side by side |
| Raw | `<pre>` with unified diff | Line-level unified diff |

**Why three modes instead of replacing side-by-side:** Side-by-side is useful for reading full spec content — the semantic view only shows what changed, not the surrounding context. Raw is useful for exact line-level review. All three serve different review needs.

**Why semantic as default:** The change detail view already defaults to semantic. Consistency across surfaces.

**Alternatives considered:**
- Two modes (semantic + raw), drop side-by-side. Rejected — side-by-side full-content reading is a distinct use case.
- No toggle, always semantic. Rejected — power users want raw diffs for exact review.

### Decision 3: View-mode state is per-session, not per-file

**Choice:** The selected view-mode persists when the user clicks different files in the spec browser list. It resets to "semantic" when the mode (current/dirty/refs) changes.

**Why:** When reviewing multiple changed specs, the user typically wants the same view mode for all of them. Switching modes (current→dirty) is a different review context, so resetting is natural.

## Risks / Trade-offs

- **Payload bloat** → `semantic_diff` adds structured JSON per changed file. Mitigated: only included for changed files (status not in unchanged/missing), same gating as the existing `semantic_summary`. For repos with 50+ changed specs the payload grows, but this is an edge case and the data is already partially there (semantic_summary).

- **Label confusion in dirty/refs mode** → `SpecDeltaView` was built for change-scoped diffs (before=baseline, after=proposed). In the spec browser, before/after semantics are HEAD vs worktree (dirty) or ref vs ref (refs). The component compares two strings and renders the delta — it doesn't label them. The spec browser's existing header already shows the before/after labels (`os-diff-col-head`). No change needed, but worth verifying the labels remain clear.

- **View-mode toggle adds toolbar complexity** → The spec browser toolbar is already dense (mode buttons, refs inputs, sort select, refresh). Adding a view-mode toggle needs to fit without crowding. Place it in the detail pane header (next to the file path), not the top toolbar — it only applies to the selected file's diff view, not the whole browser.

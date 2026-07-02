# Semantic diff in spec browser

## Source
- Origin: human
- Created: 2026-06-23T01:37:45Z
- Tags: dashboard, spec-browser, semantic-diff, consistency

## Prompt
The change detail's Specs tab already renders SpecDeltaView — the requirement/scenario-level delta from spec_parser.semantic_spec_diff. But the spec browser (current/dirty/refs mode) only shows side-by-side SpecContentView + raw unified diff. The backend (_spec_browser in plugin_api.py) already computes semantic_summary (the +/~/− counts) for changed files but discards the full semantic_diff. Wire semantic_diff into the spec-browser file payload and render SpecDeltaView there too, making diffing consistent across both views.

<!-- OPENSPEC_IDEA_ENRICHMENT_START -->
## Enrichment Report

Generated: 2026-06-23T01:38:40Z

### Problem
The change detail's Specs tab renders SpecDeltaView (requirement/scenario-level structured diff from spec_parser.semantic_spec_diff), but the spec browser (current/dirty/refs modes) only shows side-by-side SpecContentView + raw unified diff. The backend already computes semantic_summary (the +/~/− counts) for changed files in _spec_browser but discards the full semantic_diff. This means the two spec-diffing surfaces in the dashboard are inconsistent — one is structured and navigable, the other is raw text comparison.

### Proposed Direction
1. In plugin_api.py _spec_browser(), compute and include the full semantic_diff for each changed file (currently only semantic_summary is computed). The _compute_semantic_diff helper already exists and is used by _change_detail. 2. In dashboard/dist/index.js SpecsView, replace the side-by-side SpecContentView rendering for changed files with SpecDeltaView (the component already exists and is used by ChangeSpecsView). 3. Add a view-mode toggle (semantic / side-by-side / raw) so users can switch between the structured delta and the raw comparison. 4. Keep the "current" mode as-is (no diff, just SpecContentView).

### Key Questions
- Should the spec browser default to semantic diff view or keep side-by-side as default with a toggle?
- Should unchanged requirements be collapsed (like in change detail) or shown expanded since the user is browsing, not reviewing a specific change?
- Should we add a view-mode toggle (semantic / side-by-side / raw) to the spec browser toolbar, or just replace the current side-by-side with semantic?

### Feasibility
Feasibility: High

### T-Shirt Size
T-Shirt Size: S

### Size Justification
The backend helper (_compute_semantic_diff) and the frontend component (SpecDeltaView) both already exist and are used by the change detail. The work is wiring them together in the spec browser path — adding semantic_diff to the _spec_browser payload and switching the render call. No new parsing logic, no new components.

### Risks
- Larger API payload — semantic_diff adds structured JSON per changed file. For repos with many changed specs, this could bloat the response. Mitigated by only including it for changed files (status not in unchanged/missing), same as the current semantic_summary gating.
- SpecDeltaView was built for change-scoped diffs (before=baseline, after=proposed). In the spec browser dirty/refs mode, before/after semantics are different (HEAD vs worktree, or ref vs ref). The component should work as-is since it just compares two strings, but the labels might be confusing.

### Suggested Next Step
Draft a change proposal that specifies the exact payload field addition in _spec_browser and the frontend render swap, with a view-mode toggle for semantic/side-by-side/raw.
<!-- OPENSPEC_IDEA_ENRICHMENT_END -->

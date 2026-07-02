# Board search and filter

## Source
- Origin: human
- Created: 2026-06-23T01:37:46Z
- Tags: dashboard, board, ux, search

## Prompt
The kanban board has no search or filter. With many changes across ideas, draft, todo, in_progress, done, and archived columns, finding a specific change requires visual scanning. Add a text filter box that filters cards by title, name, or token across all columns. Consider also filtering by status (show/hide archived, show only a subset of columns). This is a pure frontend change in dashboard/dist/index.js — no backend changes needed since all change data is already in the board payload.

<!-- OPENSPEC_IDEA_ENRICHMENT_START -->
## Enrichment Report

Generated: 2026-06-23T01:38:41Z

### Problem
The kanban board has no search or filter capability. When a project accumulates many changes across the six lifecycle columns (ideas, draft, todo, in_progress, done, archived), finding a specific change requires manually scanning all columns. This becomes painful with 20+ changes and is a usability regression as projects mature.

### Proposed Direction
Add a search Input to the Board component toolbar (above the columns). Filter cards client-side by title, name, or token substring match. Add a column-visibility toggle (checkboxes or a Select) to show/hide individual status columns — useful for hiding archived when focusing on active work. All filtering is pure frontend in dashboard/dist/index.js — no backend changes needed since the board payload already contains all change/idea data. Implementation: add a `filterText` state variable + a `visibleColumns` set, filter `byCol` entries before rendering, and add the UI controls to the board header.

### Key Questions
- Should search filter across all projects or just the active one? (Current design is per-project, so filtering the active project's board is the natural scope.)
- Should archived changes be hidden by default with a toggle to show them, or always visible in the archived column?
- Should the filter support token-based search (e.g. typing 'os_a1b2c3' jumps to that change) or just text matching on title/name?

### Feasibility
Feasibility: High

### T-Shirt Size
T-Shirt Size: XS

### Size Justification
Pure frontend change. Add a text input, a state variable, and filter the items array before rendering. No API changes, no backend logic. The board data is already fully loaded in the component.

### Risks
- Filtering hides cards from the DOM, which could confuse deep-linking via hash tokens — if a card is filtered out but its token is in the URL hash, the detail dialog won't open. Need to either bypass the filter for hash-matched items or clear the filter when a hash token is present.
- Column toggle adds UI complexity to an already dense toolbar. Keep it minimal — maybe just an 'archived' show/hide toggle rather than per-column checkboxes.

### Suggested Next Step
Implement directly — add filter input to Board component, filter byCol entries by text match on title/name/token, add archived show/hide toggle.
<!-- OPENSPEC_IDEA_ENRICHMENT_END -->

## Context

The dashboard spec browser has several wide surfaces:

- top-level toolbar and view-mode controls
- `os-specs-grid` two-column file-list/detail layout
- side-by-side diff columns
- long spec paths and requirement/scenario text
- modal wrappers used by change/spec detail views

These are fine on desktop but break narrow screens by creating horizontal overflow or cramped controls.

## Decisions

### Decision 1: Collapse the spec browser grid on narrow screens

Use a single-column layout for the spec browser below the mobile breakpoint. The file list becomes a horizontal strip so the selected spec remains close to the detail pane without requiring a full vertical list before the content.

### Decision 2: Stack diff columns on mobile

Side-by-side content is a desktop affordance. On mobile, before/after columns and scenario-level before/after blocks stack vertically to preserve readable line lengths.

### Decision 3: Wrap long identifiers and text

Spec paths, requirement names, scenario names, step text, and card titles wrap with `overflow-wrap: anywhere` where needed. This prevents one long token or path from pushing the entire page wider than the viewport.

### Decision 4: Keep controls available

Mode toggles and toolbar groups wrap or become horizontally scrollable instead of disappearing. Users should not lose semantic/side-by-side/raw review capability just because they are on mobile.

## Risks / Trade-offs

- Horizontal file-list scrolling is still a scroll surface, but it is bounded to the list rather than the entire page.
- Side-by-side diff mode is no longer visually side-by-side on mobile; the semantic meaning is preserved by stacked before/after content.

## Context

The kanban board (`Board` component in `dashboard/dist/index.js`) renders all changes and ideas across six lifecycle columns: ideas, draft, todo, in_progress, done, archived. All data is loaded in a single payload from `GET /sources` (the `_source_payload` → `_scan()` backend). There is no search, filter, or column visibility control. The board header currently shows the repo name, a copy chip, and the repo path. The toolbar above it has source selection, refresh, edit, remove, and add buttons.

The board also interacts with hash deep-linking: `#project/token#anchor` can open a specific change's detail dialog. This is handled in `OpenSpecPage` via `useEffect` on `anchor.token`.

## Goals / Non-Goals

**Goals:**
- Add a text filter that narrows cards across all columns by title, name, or token
- Add a toggle to show/hide the archived column
- Keep the filter client-side (no backend changes)
- Preserve hash deep-linking when a filter is active

**Non-Goals:**
- Per-column show/hide checkboxes (too much UI for marginal value)
- Server-side filtering (board payload is already fully loaded)
- Filtering across projects (filter is per-active-project)
- Saved filter presets

## Decisions

### Decision 1: Filter input placement

**Choice:** Place the filter `Input` in the board header row, between the repo path and the columns. Add an archived toggle button next to it.

```
┌─────────────────────────────────────────────────────┐
│ hermes-openspec  [os_x4f2]  ~/repos/hermes-openspec │
│ [🔍 Filter by title, name, or token...] [Archived ✓]│
├──────────┬──────────┬──────────┬──────────┬─────────┤
│ Ideas    │ Draft    │ Todo     │ In Prog  │ Done    │ ...
└──────────┴──────────┴──────────┴──────────┴─────────┘
```

**Why not in the top toolbar:** The top toolbar (`Toolbar` component) is for source-level actions (select, refresh, edit, remove, add). The filter is board-scoped — it belongs with the board, not the source selector.

**Why not a collapsible panel:** A simple always-visible input is faster to use and discoverable. Collapsible panels hide functionality.

### Decision 2: Filter matching

**Choice:** Case-insensitive substring match against `title`, `name`, and `token` fields of each card.

**Why not fuzzy search:** The board typically has 10-50 cards. Substring is instant, simple, and predictable. Fuzzy adds complexity for no real benefit at this scale.

**Why not regex:** Overkill for the use case and a footgun for non-technical users.

### Decision 3: Archived toggle (not per-column checkboxes)

**Choice:** A single toggle button: "Archived ✓" / "Archived ✗". Default: visible (matches current behavior). When hidden, the archived column is not rendered and archived cards are excluded from filter results.

**Why not per-column checkboxes:** Six checkboxes in the header would be visually noisy. The archived column is the main one users want to hide — it's the largest and least relevant during active development. Other columns are always relevant.

**Alternatives considered:**
- Per-column checkboxes via a dropdown. Rejected — extra click for the common case (hide archived).
- Move archived to a separate "Archived" view tab. Rejected — changes the board navigation model. A toggle is less disruptive.

### Decision 4: Hash deep-link bypass

**Choice:** When a hash token is present in the URL, the matching card bypasses the filter. Specifically: if `anchor.token` matches a card, that card's detail dialog opens regardless of `filterText`.

**Implementation:** In the `useEffect` that handles `anchor.token` (in `OpenSpecPage`), the item lookup already searches `src.openspec.changes` and `src.openspec.ideas`. The filter only affects what's rendered in the board columns — the detail dialog opens from the `selItem` state, which is set by the hash effect, not by clicking a card. So the bypass is automatic: the filter hides the card visually, but the dialog still opens because it's driven by `selItem`, not by the card's visibility in the DOM.

**Edge case:** If the user types a filter that hides the card, then clicks the card's token in the URL hash, the dialog opens but the card isn't visible in the board. This is acceptable — the dialog is the focus, not the board. No special handling needed.

### Decision 5: Empty state

**Choice:** When the filter yields zero results, show a "No cards match '{filter}'" message in place of the columns.

**Why:** Empty columns with just "—" are confusing. An explicit message tells the user the filter is the cause, not that the project is empty.

## Risks / Trade-offs

- **Filter + hash interaction confusion** → User has a filter active, clicks a hash link, dialog opens but card is invisible in the board. Mitigated: the dialog is the focus. Could optionally clear the filter when a hash token is present, but that's surprising if the user deliberately set a filter.

- **Archived toggle state not persisted** → If the user hides archived, navigates away, and comes back, archived is visible again. Acceptable — filter state is per-session, not persistent. Persisting would require localStorage or URL params, adding complexity for marginal value.

- **Filter input adds height to the board header** → The board header is currently one row. Adding the filter makes it two rows. Minor visual change — ensure it doesn't push the columns below the fold on smaller screens. Use a compact input (sm size).

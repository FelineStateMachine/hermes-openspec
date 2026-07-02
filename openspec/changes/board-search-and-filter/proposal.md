# Board search and filter

## Summary

Add a text filter input and an archived show/hide toggle to the kanban board. The filter matches cards by title, name, or token across all columns. The archived toggle hides/shows the archived column. Pure frontend change — no backend modifications.

## Motivation

When a project accumulates 20+ changes across the six lifecycle columns (ideas, draft, todo, in_progress, done, archived), finding a specific change requires visually scanning all columns. A text filter and archived toggle make the board usable at scale.

## Design

### Frontend (`dashboard/dist/index.js`)

Add a `filterText` state variable and an `showArchived` boolean (default: true) to the `Board` component. Add a filter `Input` and an archived toggle button to the board header (between the repo name and the columns). Filter `byCol` entries before rendering: a card passes if its `title`, `name`, or `token` contains the filter text (case-insensitive). When `showArchived` is false, the archived column is hidden entirely.

### Hash interaction

When a hash token is present in the URL, bypass the filter for that specific item — clear the filter or exclude the hash-matched card from filtering so the detail dialog can open.

## Alternatives considered

- **Per-column checkboxes.** Rejected — too much UI for a dense toolbar. The archived show/hide toggle covers the main use case.
- **Server-side filtering.** Rejected — the board payload is already fully loaded. Client-side is simpler and instant.

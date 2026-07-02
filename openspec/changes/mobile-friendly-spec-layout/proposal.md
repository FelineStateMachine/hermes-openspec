# Mobile-friendly spec layout

## Summary

Make the dashboard spec browser and spec-diff views usable on narrow mobile screens. The layout should collapse wide desktop grids, keep controls reachable, and prevent long spec paths or requirement text from forcing horizontal page overflow.

## Motivation

The spec browser was designed as a desktop two-pane view: file list on the left, detail pane on the right, with optional side-by-side diff columns. On phones this creates unreadable horizontal overflow. The latest dashboard layout changes add responsive CSS for the spec browser, semantic diff view, modal body, and related controls; this change records the expected behavior in OpenSpec.

## Design

At narrow viewport widths, the spec browser uses a single-column detail layout with a horizontally scrollable file strip. Diff columns stack vertically, toolbar/control groups wrap or scroll horizontally, and long paths/requirement text wrap safely. Modal padding and body height shrink to preserve usable screen space.

## Alternatives considered

- **Hide diff modes on mobile.** Rejected: mobile users still need semantic, side-by-side, and raw review modes.
- **Keep the desktop two-column grid and rely on pinch zoom.** Rejected: it makes routine review painful and creates page-level horizontal overflow.

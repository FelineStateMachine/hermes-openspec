# Mobile-Friendly Spec Browser Layout Delta

## ADDED Requirements

### Requirement: Mobile-friendly spec browser layout
The dashboard spec browser SHALL remain usable on narrow mobile screens without page-level horizontal overflow.

#### Scenario: Spec browser collapses to one column
- **GIVEN** the dashboard is viewed on a narrow mobile viewport
- **WHEN** the user opens the spec browser
- **THEN** the file list and selected spec detail are arranged in a single-column layout instead of a fixed desktop two-column grid

#### Scenario: Spec list remains navigable
- **GIVEN** the dashboard is viewed on a narrow mobile viewport with multiple specs
- **WHEN** the spec browser renders the file list
- **THEN** the file list is horizontally scrollable within its own region and does not widen the whole page

#### Scenario: Long spec text wraps safely
- **GIVEN** a spec path, requirement name, scenario name, step text, or card title is longer than the available mobile width
- **WHEN** the dashboard renders it
- **THEN** the text wraps or truncates within its container without forcing horizontal page overflow

### Requirement: Mobile-friendly spec diff layout
The dashboard spec diff views SHALL preserve all review modes on narrow mobile screens while using readable stacked layouts where needed.

#### Scenario: Side-by-side diff stacks on mobile
- **GIVEN** the dashboard is viewed on a narrow mobile viewport
- **WHEN** the user selects the side-by-side diff view
- **THEN** the before and after diff panes stack vertically instead of requiring two columns across the viewport

#### Scenario: Semantic scenario changes stack on mobile
- **GIVEN** a semantic diff contains before and after scenario content
- **WHEN** the dashboard renders it on a narrow mobile viewport
- **THEN** the before and after scenario blocks stack vertically with readable line lengths

#### Scenario: Diff mode controls remain reachable
- **GIVEN** the dashboard is viewed on a narrow mobile viewport
- **WHEN** the user opens dirty or refs mode in the spec browser
- **THEN** semantic, side-by-side, and raw diff controls remain visible or horizontally scrollable instead of being hidden

### Requirement: Mobile-friendly dashboard modal framing
Dashboard modal and page framing SHALL adapt to narrow screens so spec content remains readable and close controls remain reachable.

#### Scenario: Mobile modal uses reduced padding
- **GIVEN** the dashboard opens a modal on a narrow mobile viewport
- **WHEN** the modal renders
- **THEN** the overlay and modal body use reduced padding and a viewport-bounded body height

#### Scenario: Mobile page avoids horizontal overflow
- **GIVEN** the dashboard is viewed on a narrow mobile viewport
- **WHEN** the page renders board, toolbar, or spec browser controls
- **THEN** the page prevents horizontal overflow while allowing bounded control groups to wrap or scroll

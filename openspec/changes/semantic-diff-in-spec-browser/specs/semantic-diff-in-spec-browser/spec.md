# Semantic Diff in Spec Browser Specification

## Purpose

Make spec diffing consistent between the change detail view and the spec browser by rendering the existing semantic requirement-level delta in both surfaces.

## Requirements

### Requirement: Semantic diff in spec browser payload

The spec browser backend (`_spec_browser()` in `dashboard/plugin_api.py`) must include the full `semantic_diff` for each changed file, computed via the existing `_compute_semantic_diff()` helper.

#### Scenario: Dirty mode with changed specs

- **GIVEN** a source with specs that differ between HEAD and the worktree
- **WHEN** the spec browser is loaded in dirty mode
- **THEN** each changed file's payload includes a `semantic_diff` field with the structured requirement/scenario delta

#### Scenario: Refs mode with changed specs

- **GIVEN** a source with specs that differ between two git refs
- **WHEN** the spec browser is loaded in refs mode with before and after refs
- **THEN** each changed file's payload includes a `semantic_diff` field

#### Scenario: Unchanged files excluded

- **GIVEN** a source with specs that are identical between the compared refs
- **WHEN** the spec browser payload is computed
- **THEN** unchanged files do not include a `semantic_diff` field (matching the existing `semantic_summary` gating)

### Requirement: View-mode toggle in spec browser frontend

The spec browser frontend (`SpecsView` in `dashboard/dist/index.js`) must provide a view-mode toggle for dirty and refs modes, allowing the user to switch between semantic, side-by-side, and raw diff views.

#### Scenario: Default to semantic view

- **GIVEN** the spec browser is in dirty or refs mode with changed files
- **WHEN** a changed file is selected
- **THEN** the semantic delta view (`SpecDeltaView`) is shown by default

#### Scenario: Switch to side-by-side

- **GIVEN** the spec browser is showing a semantic delta for a changed file
- **WHEN** the user selects "Side-by-side" from the view-mode toggle
- **THEN** the before and after spec content is rendered side-by-side using `SpecContentView`

#### Scenario: Switch to raw diff

- **GIVEN** the spec browser is showing a semantic delta for a changed file
- **WHEN** the user selects "Raw" from the view-mode toggle
- **THEN** the unified line diff is shown in a `<pre>` block

#### Scenario: Current mode unaffected

- **GIVEN** the spec browser is in current mode (no comparison)
- **WHEN** a file is selected
- **THEN** the spec content is shown via `SpecContentView` with no view-mode toggle

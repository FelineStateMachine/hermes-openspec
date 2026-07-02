# Semantic Diff in Spec Browser Delta

## ADDED Requirements

### Requirement: Semantic diff in spec browser payload
The spec browser backend SHALL include the full semantic requirement/scenario delta for changed spec files in dirty and ref comparison modes.

#### Scenario: Dirty mode with changed specs
- **GIVEN** a source with specs that differ between `HEAD` and the worktree
- **WHEN** the spec browser is loaded in dirty mode
- **THEN** each changed file payload includes a `semantic_diff` field with the structured requirement/scenario delta

#### Scenario: Ref comparison with changed specs
- **GIVEN** a source with specs that differ between two git refs
- **WHEN** the spec browser is loaded in refs mode with before and after refs
- **THEN** each changed file payload includes a `semantic_diff` field

#### Scenario: Unchanged files omitted from semantic payload
- **GIVEN** a source with specs that are identical between the compared versions
- **WHEN** the spec browser payload is computed
- **THEN** unchanged files do not include semantic diff data

### Requirement: Diff view-mode toggle in spec browser
The spec browser frontend SHALL provide a view-mode toggle for dirty and refs modes so maintainers can switch between semantic, side-by-side, and raw diff views.

#### Scenario: Default to semantic view
- **GIVEN** the spec browser is in dirty or refs mode with a changed file selected
- **WHEN** the detail pane renders
- **THEN** the semantic delta view is shown by default

#### Scenario: Switch to side-by-side
- **GIVEN** the spec browser is showing a semantic delta for a changed file
- **WHEN** the user selects the side-by-side mode
- **THEN** the before and after spec content are rendered side by side

#### Scenario: Switch to raw diff
- **GIVEN** the spec browser is showing a semantic delta for a changed file
- **WHEN** the user selects the raw mode
- **THEN** the unified line diff is shown in a preformatted block

#### Scenario: Current mode unaffected
- **GIVEN** the spec browser is in current mode
- **WHEN** a file is selected
- **THEN** the spec content is shown without a diff view-mode toggle

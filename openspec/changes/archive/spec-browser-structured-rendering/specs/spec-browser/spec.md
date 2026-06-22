# Spec Browser Delta — Structured Rendering

## MODIFIED Requirements

### Requirement: Dirty worktree diff mode
The dashboard API SHALL compare a git ref to current worktree specs when dirty mode is requested, and the UI SHALL render diffs using structured spec content views.

#### Scenario: Dirty diff defaults
- **WHEN** dirty mode is requested without an explicit before ref
- **THEN** the API compares `HEAD` to the working tree

#### Scenario: Dirty diff filters unchanged specs
- **GIVEN** some specs match the selected before ref exactly
- **WHEN** dirty mode is requested
- **THEN** unchanged specs are omitted from the returned files list

#### Scenario: Dirty diff entry
- **GIVEN** a spec was added, modified, or deleted relative to the before ref
- **WHEN** dirty mode is requested
- **THEN** the API returns before content, after content, status, changed flag, unified diff, and available timestamps for that spec

#### Scenario: Dirty mode structured rendering
- **WHEN** the spec browser is in dirty mode and a changed spec is selected
- **THEN** the before and after panels render using `SpecContentView` with structured requirement and scenario sections instead of raw markdown

### Requirement: Ref-to-ref diff mode
The dashboard API SHALL compare specs between two explicit git refs when both before and after refs are supplied, and the UI SHALL render diffs using structured spec content views.

#### Scenario: Valid ref comparison
- **GIVEN** both before and after refs are supplied
- **WHEN** the dashboard requests the spec browser
- **THEN** the API returns mode `refs`, both labels, all spec paths present in either ref, per-spec status, before content, after content, changed flag, and unified diff when changed

#### Scenario: Incomplete ref comparison
- **WHEN** only one of before or after is supplied outside dirty mode
- **THEN** the API rejects the request with a 400-level error explaining that both refs are required

#### Scenario: Refs mode structured rendering
- **WHEN** the spec browser is in refs mode and a changed spec is selected
- **THEN** the before and after panels render using `SpecContentView` with structured requirement and scenario sections instead of raw markdown

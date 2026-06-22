# Spec Browser Structured Rendering Delta

## ADDED Requirements

### Requirement: Semantic summary in spec list
The dashboard API SHALL include a `semantic_summary` field with requirement-level added/modified/removed counts for each spec in dirty and refs modes, and the UI SHALL display it compactly in the spec list.

#### Scenario: Backend computes semantic summary
- **GIVEN** a spec has been modified between the before and after refs
- **WHEN** the spec browser API returns entries in dirty or refs mode
- **THEN** each changed entry includes a `semantic_summary` field with `added`, `modified`, and `removed` requirement counts

#### Scenario: Spec list displays summary
- **GIVEN** a spec list entry has a `semantic_summary` with non-zero counts
- **WHEN** the spec list renders in dirty or refs mode
- **THEN** the entry displays a compact summary (e.g. "+2 req, ~1, -0") alongside the existing status badge

#### Scenario: No summary in current mode
- **WHEN** the spec browser is in current mode (no diff)
- **THEN** spec list entries do not display a semantic summary because there is no comparison

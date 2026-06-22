# Change Specs Semantic Diff View Delta

## ADDED Requirements

### Requirement: Semantic delta view component
The dashboard UI SHALL render a `SpecDeltaView` component that displays the semantic diff as a summary-first view with requirement-level sections.

#### Scenario: Delta summary
- **WHEN** the delta view renders for a modified spec
- **THEN** it shows a summary line indicating how many requirements were added, modified, and removed

#### Scenario: Added requirements section
- **GIVEN** the semantic diff contains requirements in `added`
- **WHEN** the delta view renders
- **THEN** each added requirement is shown with its description and scenarios, marked with an `added` badge

#### Scenario: Modified requirements section
- **GIVEN** the semantic diff contains requirements in `modified`
- **WHEN** the delta view renders
- **THEN** each modified requirement shows before/after description changes and scenario-level deltas (added/modified/removed scenarios)

#### Scenario: Removed requirements section
- **GIVEN** the semantic diff contains requirements in `removed`
- **WHEN** the delta view renders
- **THEN** each removed requirement is shown with its description and scenarios, marked with a `removed` badge

#### Scenario: Unchanged requirements collapsed
- **GIVEN** the semantic diff contains requirements in `unchanged`
- **WHEN** the delta view renders
- **THEN** unchanged requirements are collapsed or hidden by default to reduce noise

### Requirement: Raw diff fallback
The dashboard UI SHALL provide the unified line diff as a collapsible section at the bottom of the semantic delta view.

#### Scenario: Collapsible raw diff
- **WHEN** the delta view renders for a modified spec
- **THEN** a collapsible "raw diff" section appears at the bottom containing the unified line diff, collapsed by default

### Requirement: Replace side-by-side view
The dashboard UI SHALL use the semantic delta view instead of side-by-side full specs for the change > Specs diff mode.

#### Scenario: Diff mode renders delta view
- **WHEN** the user selects "Diff vs current" in the change > Specs tab
- **THEN** the `SpecDeltaView` component renders instead of the previous side-by-side `SpecContentView` + unified diff layout

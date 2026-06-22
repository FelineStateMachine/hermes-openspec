# Change Board Delta — Semantic Spec Diff in Change Detail

## MODIFIED Requirements

### Requirement: Change detail API
The dashboard API SHALL expose full detail for a selected change, including a semantic diff for each delta spec.

#### Scenario: Existing change detail
- **GIVEN** a selected source contains the requested change
- **WHEN** the dashboard requests change detail
- **THEN** the API returns the change name, title, status, archive flag, task stats, proposal markdown, design markdown, tasks markdown, and delta spec entries

#### Scenario: Delta spec comparison
- **GIVEN** a change contains delta spec files under its `specs/` directory
- **WHEN** the API returns change detail
- **THEN** each delta spec entry includes relative path, proposed content, current worktree spec content when present, status, a unified diff when content changed, and a `semantic_diff` field with the structured requirement-level delta

#### Scenario: Semantic diff for new spec
- **GIVEN** a change contains a delta spec with no baseline spec
- **WHEN** the API returns change detail
- **THEN** the `semantic_diff` field has status `added` with all requirements in `added`

#### Scenario: Missing change detail
- **WHEN** the dashboard requests a change that does not exist in the selected source
- **THEN** the API returns a not-found response

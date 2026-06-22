# Semantic Spec Diff Delta

## ADDED Requirements

### Requirement: Shared spec parser
The plugin SHALL provide a `_parse_spec(md)` Python function that parses OpenSpec spec markdown into structured data: title, purpose, and a list of requirements, each with a name, description, and list of scenarios, each scenario with a name and steps.

#### Scenario: Parse a well-formed spec
- **GIVEN** a spec markdown file with `# Title`, `## Purpose`, `### Requirement:` headers, and `#### Scenario:` headers with `**GIVEN**`/`**WHEN**`/`**THEN**` steps
- **WHEN** `_parse_spec` is called with the markdown content
- **THEN** it returns a dict with `title`, `purpose`, and `requirements` list, where each requirement has `name`, `description`, and `scenarios`, and each scenario has `name` and `steps`

#### Scenario: Parse a spec with no requirements
- **GIVEN** a spec markdown file with only a title and purpose, no `### Requirement:` headers
- **WHEN** `_parse_spec` is called with the markdown content
- **THEN** it returns a dict with `title`, `purpose`, and an empty `requirements` list

#### Scenario: Parse empty or None input
- **WHEN** `_parse_spec` is called with an empty string or None
- **THEN** it returns a dict with empty `title`, empty `purpose`, and empty `requirements` list

### Requirement: Semantic spec diff function
The plugin SHALL provide a `_semantic_spec_diff(before_md, after_md)` function that compares two parsed specs and returns a structured delta at the requirement and scenario level.

#### Scenario: Added requirement
- **GIVEN** the after spec contains a requirement that the before spec does not
- **WHEN** `_semantic_spec_diff` is called
- **THEN** the requirement appears in `requirements.added` with its full description and scenarios

#### Scenario: Removed requirement
- **GIVEN** the before spec contains a requirement that the after spec does not
- **WHEN** `_semantic_spec_diff` is called
- **THEN** the requirement appears in `requirements.removed` with its full description and scenarios

#### Scenario: Modified requirement description
- **GIVEN** a requirement exists in both specs with the same name but different descriptions
- **WHEN** `_semantic_spec_diff` is called
- **THEN** the requirement appears in `requirements.modified` with `before` and `after` description fields

#### Scenario: Scenario-level delta in modified requirement
- **GIVEN** a requirement exists in both specs with the same name but different scenarios
- **WHEN** `_semantic_spec_diff` is called
- **THEN** the modified entry includes `scenarios_added`, `scenarios_modified`, and `scenarios_removed` lists

#### Scenario: Unchanged requirement
- **GIVEN** a requirement exists in both specs with identical descriptions and scenarios
- **WHEN** `_semantic_spec_diff` is called
- **THEN** the requirement name appears in `requirements.unchanged`

#### Scenario: No baseline exists
- **GIVEN** the before spec is None or empty (new spec being added)
- **WHEN** `_semantic_spec_diff` is called
- **THEN** all requirements appear in `requirements.added` and the overall status is `added`

### Requirement: openspec_spec_diff agent tool
The plugin SHALL provide an `openspec_spec_diff` tool that compares a change's delta spec against its baseline, or a worktree spec against its HEAD version, and returns the structured semantic delta plus a unified line diff fallback.

#### Scenario: Diff a change spec against baseline
- **GIVEN** a change contains a delta spec under `openspec/changes/<change>/specs/<spec>/spec.md` and a baseline spec exists at `openspec/specs/<spec>/spec.md`
- **WHEN** an agent calls `openspec_spec_diff` with `workdir`, `spec`, and `change`
- **THEN** the tool returns the semantic delta between the change spec and the baseline spec, including overall status, requirements delta, and a `line_diff` unified diff field

#### Scenario: Diff a worktree spec against HEAD
- **GIVEN** a baseline spec exists at `openspec/specs/<spec>/spec.md` and has been modified in the worktree
- **WHEN** an agent calls `openspec_spec_diff` with `workdir` and `spec` (no `change`)
- **THEN** the tool returns the semantic delta between the HEAD version (via git) and the worktree version

#### Scenario: New spec with no baseline
- **GIVEN** a change contains a delta spec but no baseline spec exists
- **WHEN** an agent calls `openspec_spec_diff` with `workdir`, `spec`, and `change`
- **THEN** the tool returns status `added` with all requirements in `requirements.added` and an empty `line_diff`

#### Scenario: Missing change spec
- **WHEN** an agent calls `openspec_spec_diff` with a `change` that does not contain the requested `spec`
- **THEN** the tool returns `ok: false` with an error explaining the change spec was not found

#### Scenario: Filesystem-backed availability
- **GIVEN** no OpenSpec CLI binary is available
- **WHEN** Hermes registers plugin tools
- **THEN** `openspec_spec_diff` is still available because it reads spec files directly from the filesystem

#### Scenario: Git unavailable for HEAD comparison
- **GIVEN** `openspec_spec_diff` is called without `change` (HEAD comparison mode) and git is unavailable
- **THEN** the tool returns `ok: false` with an error explaining git is required for worktree-vs-HEAD comparison

# Agent OpenSpec Tools Delta

## MODIFIED Requirements

### Requirement: Spec lifecycle tools
The plugin SHALL provide filesystem-backed tools for creating, reading, and listing specs so agents can manage specs as first-class artifacts without the OpenSpec CLI binary.

#### Scenario: Create a baseline spec
- **GIVEN** a project with an `openspec/specs/` directory
- **WHEN** an agent calls `openspec_spec_create` with a spec name, title, purpose, and requirements array (each with name, description, and optional scenarios)
- **THEN** the tool writes a properly formatted `openspec/specs/<name>/spec.md` using `### Requirement:` and `#### Scenario:` markdown and returns `ok: true` with the spec name and relative path

#### Scenario: Create a change-scoped spec
- **GIVEN** a project with an active change
- **WHEN** an agent calls `openspec_spec_create` with a `change` parameter and a spec name
- **THEN** the tool writes the spec under `openspec/changes/<change>/specs/<name>/spec.md` instead of the baseline directory

#### Scenario: Refuse to overwrite existing spec
- **GIVEN** a spec already exists at the target path
- **WHEN** an agent calls `openspec_spec_create` without a `force` flag
- **THEN** the tool returns `ok: false` and does not modify the existing file

#### Scenario: Show a spec as structured JSON
- **WHEN** an agent calls `openspec_spec_show` with a spec name and optional `change` id
- **THEN** the tool reads and parses the spec using `spec_parser.parse_spec` and returns `ok: true` with the title, purpose, and an array of requirements (each with name, description, and scenarios)

#### Scenario: Show missing spec
- **WHEN** an agent calls `openspec_spec_show` for a spec that does not exist
- **THEN** the tool returns `ok: false` with a clear error

#### Scenario: List baseline specs
- **WHEN** an agent calls `openspec_spec_list` without a `change` parameter
- **THEN** the tool returns `ok: true` with an array of spec names found under `openspec/specs/`

#### Scenario: List change-scoped specs
- **WHEN** an agent calls `openspec_spec_list` with a `change` parameter
- **THEN** the tool returns `ok: true` with an array of spec names found under `openspec/changes/<change>/specs/`

#### Scenario: List specs when none exist
- **GIVEN** the target specs directory is empty or missing
- **WHEN** an agent calls `openspec_spec_list`
- **THEN** the tool returns `ok: true` with an empty array

#### Scenario: Invalid workdir
- **WHEN** any spec tool is called with a missing or non-directory workdir
- **THEN** the tool returns `ok: false` and does not perform filesystem operations

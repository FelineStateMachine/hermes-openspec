## MODIFIED Requirements

### Requirement: Artifact listing and inspection
The plugin SHALL provide tools that map directly to OpenSpec list/show/status/instructions workflows while smoothing known CLI rough edges that would otherwise block fresh-repository agent workflows.

#### Scenario: List changes or specs
- **WHEN** an agent calls `openspec_list` with kind `changes` or `specs`
- **THEN** the tool invokes the OpenSpec CLI JSON list command for that kind and respects supported sort options

#### Scenario: Show a change or spec
- **WHEN** an agent calls `openspec_show` with a target name and optional flags
- **THEN** the tool invokes the OpenSpec CLI JSON show command with the requested type, delta, requirements, scenario, or requirement filters

#### Scenario: Validate artifacts
- **WHEN** an agent calls `openspec_validate`
- **THEN** the tool invokes the OpenSpec CLI validation command with strict JSON non-interactive output and the requested target or scope

#### Scenario: Retrieve implementation instructions
- **WHEN** an agent calls `openspec_instructions`
- **THEN** the tool returns OpenSpec's enriched instructions for the requested artifact, schema, and optional change

#### Scenario: Accept singular spec artifact alias
- **WHEN** an agent calls `openspec_instructions` with artifact `spec`
- **THEN** the tool treats it as the OpenSpec CLI artifact `specs`

#### Scenario: Fresh repository instructions fallback
- **GIVEN** a repository has been initialized but contains no changes
- **WHEN** an agent calls `openspec_instructions` for a known artifact
- **THEN** the tool returns `ok: true` with template-backed guidance for that artifact instead of failing only because no change exists

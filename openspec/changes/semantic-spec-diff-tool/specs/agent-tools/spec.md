# Agent Tools Delta — Semantic Spec Diff

## MODIFIED Requirements

### Requirement: Artifact listing and inspection
The plugin SHALL provide tools that map directly to OpenSpec list/show/status/instructions workflows while smoothing known CLI rough edges that would otherwise block fresh-repository agent workflows and SHALL expose a filesystem-backed semantic spec diff tool for comparing specs at the requirement and scenario level without the CLI.

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

#### Scenario: Semantic spec diff
- **WHEN** an agent calls `openspec_spec_diff` with `workdir`, `spec`, and optional `change`
- **THEN** the tool returns a structured semantic delta at the requirement and scenario level plus a unified line diff fallback, without requiring the OpenSpec CLI binary

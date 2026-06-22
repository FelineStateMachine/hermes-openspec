# Agent OpenSpec Tools

## Purpose

The plugin SHALL expose OpenSpec-aware Hermes tools that let agents discover, inspect, validate, and act on repo-local OpenSpec artifacts without manually assembling shell commands. Tools are expected to be safe for maintainers to use across multiple registered repositories and predictable enough for other agents to depend on.
## Requirements
### Requirement: Registered-source context resolution
The plugin SHALL provide an `openspec_context` tool that resolves user-facing OpenSpec identifiers into the source repository path and relevant artifact content.

#### Scenario: Resolve a bare source name
- **GIVEN** a source is registered with a vanity name or falls back to its path basename
- **WHEN** an agent calls `openspec_context` with that source name
- **THEN** the tool returns the repository path, workdir hint, active changes with tokens, and current specs with tokens

#### Scenario: Resolve a change token
- **GIVEN** a registered source contains an active or archived change directory with `proposal.md`
- **WHEN** an agent calls `openspec_context` with `<source>/<os_token>` for that change
- **THEN** the tool returns the change name, archive status, proposal content, tasks content, design content, and each delta spec file's relative path and content

#### Scenario: Resolve a spec token
- **GIVEN** a registered source contains a spec under `openspec/specs/`
- **WHEN** an agent calls `openspec_context` with `<source>/<os_token>` for that spec
- **THEN** the tool returns the spec path and full spec content

#### Scenario: Missing source or artifact
- **WHEN** an agent calls `openspec_context` with an unknown source or unknown artifact token
- **THEN** the tool returns `ok: false` and a direct error explaining what could not be resolved

### Requirement: CLI-backed tool gating
The plugin SHALL only expose CLI-backed tools when an executable OpenSpec CLI binary is available.

#### Scenario: OpenSpec binary available
- **GIVEN** `OPENSPEC_BIN`, `PATH`, or the user's `~/.npm-global/bin/openspec` points to an executable binary
- **WHEN** Hermes registers plugin tools
- **THEN** `openspec_list`, `openspec_show`, `openspec_validate`, `openspec_status`, and `openspec_instructions` are available

#### Scenario: OpenSpec binary unavailable
- **GIVEN** no executable OpenSpec CLI binary is found
- **WHEN** Hermes registers plugin tools
- **THEN** only `openspec_context` remains available because it reads the registry database and filesystem directly

### Requirement: CLI command execution contract
CLI-backed tools SHALL execute OpenSpec commands in a resolved project workdir and return structured JSON-compatible results.

#### Scenario: Successful command
- **WHEN** a CLI-backed tool runs an OpenSpec command successfully
- **THEN** the tool returns `ok: true`, the command, workdir, exit code, parsed stdout when stdout is JSON, stderr, and truncation status

#### Scenario: Failed command
- **WHEN** a CLI-backed tool receives a non-zero OpenSpec CLI exit code
- **THEN** the tool returns `ok: false` with the same command, workdir, stdout, stderr, exit code, and truncation status

#### Scenario: Invalid workdir
- **WHEN** a CLI-backed tool is called with a missing or non-directory workdir
- **THEN** the tool returns `ok: false` and does not execute the OpenSpec CLI

#### Scenario: Command timeout
- **WHEN** an OpenSpec CLI command runs longer than the configured timeout
- **THEN** the tool returns `ok: false` with the command, workdir, and timeout error

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


# Bundled OpenSpec Workflow Skills and CLI Passthrough Delta

## ADDED Requirements

### Requirement: Bundle upstream workflow skills
The plugin SHALL bundle all upstream OpenSpec workflow skills as Hermes plugin skills and register them during plugin load.

#### Scenario: Skills registered on plugin load
- **GIVEN** the plugin is installed and enabled
- **WHEN** Hermes starts and calls `register(ctx)`
- **THEN** all bundled workflow skills are registered and appear in the Hermes skill catalog

#### Scenario: Skill content matches upstream format
- **GIVEN** the bundled skill files exist in `skills/<name>/SKILL.md`
- **WHEN** a contributor inspects a bundled skill
- **THEN** the skill uses upstream OpenSpec-style YAML frontmatter and workflow instructions without being rewritten around plugin-specific tool shapes

#### Scenario: Skills call CLI directly via terminal
- **GIVEN** an upstream workflow skill is loaded in a session
- **WHEN** the skill instructs the agent to run an OpenSpec workflow command
- **THEN** the agent may execute the OpenSpec CLI directly rather than routing the workflow through plugin wrapper tools

### Requirement: OpenSpec CLI passthrough tool
The plugin SHALL provide an `openspec_cli` passthrough tool that runs the OpenSpec CLI binary and returns raw command output.

#### Scenario: Tool appears when CLI is installed
- **GIVEN** the `openspec` binary is available on PATH or via `OPENSPEC_BIN`
- **WHEN** the plugin registers tools
- **THEN** `openspec_cli` is available in the agent tool list

#### Scenario: Tool hidden when CLI is not installed
- **GIVEN** the `openspec` binary is not available
- **WHEN** the plugin registers tools
- **THEN** `openspec_cli` is not exposed

#### Scenario: JSON output mode
- **GIVEN** the `openspec` CLI is installed
- **WHEN** the agent calls `openspec_cli` with a command and `json_output: true`
- **THEN** the tool runs the command with JSON output enabled and returns the raw CLI JSON payload

#### Scenario: Raw output mode
- **GIVEN** the `openspec` CLI is installed
- **WHEN** the agent calls `openspec_cli` with `json_output: false`
- **THEN** the tool runs the command without forcing JSON output and returns the raw text payload

#### Scenario: Workdir support
- **GIVEN** a project at a specific path
- **WHEN** the agent calls `openspec_cli` with that workdir
- **THEN** the CLI command runs in that directory

### Requirement: Layer separation documentation
The plugin SHALL include documentation explaining the boundary between bundled workflow skills, CLI access, plugin tools, and the dashboard.

#### Scenario: Layer doc exists
- **GIVEN** the plugin repository is checked out
- **WHEN** a contributor reads `docs/layers.md`
- **THEN** the document explains that workflow skills call the OpenSpec CLI directly, plugin tools return plugin-specific JSON shapes, and both interfaces coexist by design

#### Scenario: README references layer doc
- **GIVEN** the plugin README is read
- **WHEN** the reader looks for architecture information
- **THEN** the README links to `docs/layers.md` and summarizes the layer architecture

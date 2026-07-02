# Bundled OpenSpec Workflow Skills + CLI Passthrough Specification

## Purpose

Bundle upstream OpenSpec workflow skills as Hermes plugin skills and add an `openspec_cli` passthrough tool, creating a clean layer separation between workflow prompts (skills), CLI access, ad-hoc query tools, and the dashboard.

## Requirements

### Requirement: Bundle 11 upstream workflow skills

The plugin must bundle all 11 upstream OpenSpec workflow skills as Hermes plugin skills, registered via `ctx.register_skill()`.

#### Scenario: Skills registered on plugin load

- **GIVEN** the plugin is installed and enabled
- **WHEN** Hermes starts and calls `register(ctx)`
- **THEN** all 11 skills (`openspec-propose`, `openspec-explore`, `openspec-apply-change`, `openspec-archive-change`, `openspec-new-change`, `openspec-continue-change`, `openspec-ff-change`, `openspec-verify-change`, `openspec-sync-specs`, `openspec-bulk-archive-change`, `openspec-onboard`) are registered and appear in `hermes skills list`

#### Scenario: Skill content matches upstream

- **GIVEN** the bundled skill files exist in `skills/<name>/SKILL.md`
- **WHEN** the skill content is compared to the upstream `generateSkillContent()` output
- **THEN** the YAML frontmatter and instructions body match the upstream format without modification

#### Scenario: Agent auto-loads skill on intent match

- **GIVEN** the `openspec-propose` skill is registered
- **WHEN** the user says "propose a change for dark mode"
- **THEN** the agent loads the `openspec-propose` skill and follows its workflow

#### Scenario: Skills call CLI directly via terminal

- **GIVEN** an upstream skill is loaded in a session
- **WHEN** the skill instructs the agent to run `openspec new change "<name>"`
- **THEN** the agent executes the command via the `terminal` tool, not via plugin wrapper tools

### Requirement: openspec_cli passthrough tool

The plugin must provide an `openspec_cli` tool that runs the `openspec` CLI binary and returns raw output.

#### Scenario: Tool appears when CLI is installed

- **GIVEN** the `openspec` binary is available on PATH or via `OPENSPEC_BIN`
- **WHEN** the plugin registers tools
- **THEN** `openspec_cli` appears in the agent's tool list

#### Scenario: Tool hidden when CLI is not installed

- **GIVEN** the `openspec` binary is not available
- **WHEN** the plugin registers tools
- **THEN** `openspec_cli` does not appear in the agent's tool list

#### Scenario: JSON output mode

- **GIVEN** the `openspec` CLI is installed
- **WHEN** the agent calls `openspec_cli` with `command: "status --change my-change"` and `json_output: true`
- **THEN** the tool runs `openspec status --change my-change --json` and returns the raw JSON output from the CLI

#### Scenario: Raw output mode

- **GIVEN** the `openspec` CLI is installed
- **WHEN** the agent calls `openspec_cli` with `command: "list"` and `json_output: false`
- **THEN** the tool runs `openspec list` (without `--json`) and returns the raw text output

#### Scenario: Workdir support

- **GIVEN** a project at a specific path
- **WHEN** the agent calls `openspec_cli` with `workdir: "/path/to/project"`
- **THEN** the CLI command runs with that path as the working directory

### Requirement: Layer separation documentation

The plugin must include documentation explaining the boundary between skills, CLI, plugin tools, and dashboard.

#### Scenario: Layer doc exists

- **GIVEN** the plugin is installed
- **WHEN** a contributor reads `docs/layers.md`
- **THEN** the doc explains that skills call the CLI directly via terminal, plugin tools return different JSON shapes, and the two coexist by design

#### Scenario: README references layer doc

- **GIVEN** the plugin README is read
- **WHEN** the reader looks for architecture information
- **THEN** the README links to `docs/layers.md` and mentions the layer architecture

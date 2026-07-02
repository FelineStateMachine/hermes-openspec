# Slash Commands /opsx:* Specification

## Purpose

Provide power-user slash command shortcuts that route to the plugin's existing tool handlers, matching the upstream OpenSpec command set for familiarity.

## Requirements

### Requirement: Core profile commands

The plugin must register four core `/opsx:*` slash commands that cover the default spec-driven workflow.

#### Scenario: /opsx:propose creates a change

- **GIVEN** the plugin is installed and a workdir or project is specified
- **WHEN** the user types `/opsx:propose add-dark-mode`
- **THEN** `openspec_change_create` is dispatched with the parsed change name and `openspec_instructions` is dispatched with `artifact=proposal`, and the combined result is returned

#### Scenario: /opsx:explore creates an idea

- **GIVEN** the plugin is installed
- **WHEN** the user types `/opsx:explore "add dark mode support"`
- **THEN** `openspec_idea_create` is dispatched with the topic as title and prompt

#### Scenario: /opsx:apply lists tasks and instructions

- **GIVEN** a change exists with tasks
- **WHEN** the user types `/opsx:apply add-dark-mode`
- **THEN** `openspec_task_list` is dispatched and incomplete tasks are listed, followed by `openspec_instructions` with `artifact=apply`

#### Scenario: /opsx:archive validates then archives

- **GIVEN** a change exists
- **WHEN** the user types `/opsx:archive add-dark-mode`
- **THEN** `openspec_validate` is dispatched first, and if validation passes, `openspec_change_archive` is dispatched

#### Scenario: /opsx:archive blocks on validation errors

- **GIVEN** a change has validation errors
- **WHEN** the user types `/opsx:archive add-dark-mode`
- **THEN** the validation errors are reported and `openspec_change_archive` is not dispatched

### Requirement: Expanded workflow commands

The plugin must register seven expanded `/opsx:*` slash commands for step-by-step and batch workflows.

#### Scenario: /opsx:new creates bare scaffold

- **GIVEN** the plugin is installed
- **WHEN** the user types `/opsx:new add-feature`
- **THEN** `openspec_change_create` is dispatched and the change scaffold is created without promotion

#### Scenario: /opsx:continue shows next artifact

- **GIVEN** a change exists with some artifacts missing
- **WHEN** the user types `/opsx:continue add-feature`
- **THEN** `openspec_status` is dispatched and the next missing artifact is determined, and `openspec_instructions` is dispatched for that artifact

#### Scenario: /opsx:ff creates and promotes

- **GIVEN** the plugin is installed
- **WHEN** the user types `/opsx:ff add-feature`
- **THEN** `openspec_change_create` is dispatched (if the change doesn't exist), then `openspec_change_promote` is dispatched

#### Scenario: /opsx:verify checks three dimensions

- **GIVEN** a change exists with tasks and specs
- **WHEN** the user types `/opsx:verify add-feature`
- **THEN** `openspec_validate`, `openspec_status`, and `openspec_task_list` are dispatched and the combined results are reported

#### Scenario: /opsx:sync shows delta spec diffs

- **GIVEN** a change has delta specs
- **WHEN** the user types `/opsx:sync add-feature`
- **THEN** `openspec_spec_list` is dispatched for the change, and `openspec_spec_diff` is dispatched for each delta spec, and the diffs are summarized

#### Scenario: /opsx:bulk-archive archives multiple

- **GIVEN** multiple changes exist
- **WHEN** the user types `/opsx:bulk-archive change-a change-b change-c`
- **THEN** `openspec_change_archive` is dispatched for each change in sequence, and per-change results are reported

#### Scenario: /opsx:onboard prints workflow guide

- **GIVEN** the plugin is installed
- **WHEN** the user types `/opsx:onboard`
- **THEN** a static workflow guide is returned with no tool dispatches

### Requirement: Target resolution via flags

All `/opsx:*` commands (except `/opsx:onboard`) must accept `--workdir` and `--project` flags for repo targeting.

#### Scenario: --workdir flag

- **GIVEN** the user wants to target a specific repo
- **WHEN** the user types `/opsx:propose add-feature --workdir ~/repos/my-project`
- **THEN** the tool dispatches include `workdir` set to the expanded path

#### Scenario: --project flag

- **GIVEN** the user wants to target a registered OpenSpec source
- **WHEN** the user types `/opsx:propose add-feature --project my-project`
- **THEN** the tool dispatches include `identifier` set to the project name

#### Scenario: No flag uses cwd

- **GIVEN** no `--workdir` or `--project` flag is provided
- **WHEN** the user types `/opsx:propose add-feature`
- **THEN** the tool dispatches use the current working directory as the workdir

### Requirement: Command registration

The plugin must register all commands via `ctx.register_command()` during `register()`.

#### Scenario: Commands appear in help

- **GIVEN** the plugin is installed and enabled
- **WHEN** the user types `/help`
- **THEN** all 11 `/opsx:*` commands are listed with their descriptions

#### Scenario: Commands work in gateway

- **GIVEN** the plugin is installed and the gateway is running
- **WHEN** a user types `/opsx:onboard` in Discord or Telegram
- **THEN** the workflow guide is returned as a message

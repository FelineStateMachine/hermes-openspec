# Agent OpenSpec Tools Delta

## MODIFIED Requirements

### Requirement: Artifact listing and inspection
The plugin SHALL provide tools that map directly to OpenSpec list/show/status/instructions workflows while smoothing known CLI rough edges that would otherwise block fresh-repository agent workflows and SHALL expose lifecycle write tools with noun-action naming.

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

#### Scenario: Create an idea artifact
- **WHEN** an agent calls `openspec_idea_create` with a valid project/workdir, title, prompt, and optional origin/tags/notes
- **THEN** the tool creates a markdown idea under `openspec/ideas/`, uses a safe deterministic slug with collision handling, and returns `ok: true` with the idea slug, relative path, absolute path, and parsed metadata

#### Scenario: Refuse invalid idea creation
- **WHEN** an agent calls `openspec_idea_create` with a missing project, empty title, empty prompt, or unsafe path input
- **THEN** the tool returns `ok: false` with a direct validation error and does not write an idea file

#### Scenario: Enrich an existing idea
- **GIVEN** an idea exists under `openspec/ideas/`
- **WHEN** an agent calls `openspec_idea_enrich` with structured enrichment fields
- **THEN** the tool writes or updates an enrichment report containing problem, proposed direction, key questions, feasibility, T-shirt size, size justification, risks, and suggested next step

#### Scenario: Promote an idea into a change
- **GIVEN** an idea exists under `openspec/ideas/`
- **WHEN** an agent calls `openspec_idea_promote` with a valid change id
- **THEN** the tool creates an OpenSpec change scaffold that includes proposal, tasks, metadata, and a valid placeholder spec delta, preserves traceability to the source idea, and returns the created artifact paths

#### Scenario: Create a change directly
- **WHEN** an agent calls `openspec_change_create` with a valid change id, title, and summary
- **THEN** the tool creates a draft OpenSpec change scaffold with proposal metadata and optional tasks/spec placeholder artifacts according to the supplied inputs

#### Scenario: Promote a draft change to todo
- **GIVEN** an active change has proposal content but no task checklist
- **WHEN** an agent calls `openspec_change_promote` with task descriptions
- **THEN** the tool creates or updates `tasks.md`, ensures at least one valid spec delta exists, and returns the change status as `todo`

#### Scenario: List tasks for a change
- **GIVEN** a change has a `tasks.md` checklist
- **WHEN** an agent calls `openspec_task_list`
- **THEN** the tool returns ordered task ids, text, status, and aggregate completion counts

#### Scenario: Set task status
- **GIVEN** a change has a `tasks.md` checklist
- **WHEN** an agent calls `openspec_task_set_status` with task ids and status `todo` or `done`
- **THEN** the tool updates only the requested checklist items and returns refreshed task counts and derived change status

#### Scenario: Archive a completed change
- **GIVEN** an active change has all tasks complete
- **WHEN** an agent calls `openspec_change_archive`
- **THEN** the tool moves the change under `openspec/changes/archive/`, refuses incomplete tasks unless forced, and returns the archived path

#### Scenario: Unarchive a change
- **GIVEN** a change exists under `openspec/changes/archive/`
- **WHEN** an agent calls `openspec_change_unarchive`
- **THEN** the tool moves the change back under `openspec/changes/` and refuses to overwrite an active change unless forced

#### Scenario: Refuse unsafe lifecycle overwrites
- **GIVEN** a target idea, change, task, or archive path would overwrite existing data without explicit force
- **WHEN** an agent calls any lifecycle write tool
- **THEN** the tool returns `ok: false` and preserves existing files

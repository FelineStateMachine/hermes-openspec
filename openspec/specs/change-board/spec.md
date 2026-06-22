# OpenSpec Change Board

## Purpose

The dashboard plugin SHALL present repo-local OpenSpec work as a maintainer-facing board that surfaces ideas, active changes, archived changes, task progress, and rich artifact details. The board exists to make OpenSpec state inspectable without leaving the Hermes dashboard.

## Requirements

### Requirement: Board scan model
The dashboard API SHALL scan each initialized source's `openspec/` directory into board data without persisting change or spec records in the plugin database.

#### Scenario: Active change scan
- **GIVEN** a directory exists under `openspec/changes/` with a `proposal.md`
- **WHEN** the source is scanned
- **THEN** the API includes it as a change with name, token, title, status, artifact presence flags, and task stats when available

#### Scenario: Archived change scan
- **GIVEN** a directory exists under `openspec/changes/archive/` with a `proposal.md`
- **WHEN** the source is scanned
- **THEN** the API includes it as an archived change and assigns it the archived status

#### Scenario: Idea scan
- **GIVEN** a markdown file exists under `openspec/ideas/`
- **WHEN** the source is scanned
- **THEN** the API includes it as an idea with name, token, title, and ideas status

#### Scenario: Current spec scan
- **GIVEN** a markdown file exists under `openspec/specs/`
- **WHEN** the source is scanned
- **THEN** the API includes it as a current spec with relative path, token, and title

### Requirement: Change status derivation
The dashboard API SHALL derive change board status from OpenSpec files and task completion rather than storing status manually.

#### Scenario: Draft status
- **GIVEN** a change has a proposal but no tasks file or no parseable task stats
- **WHEN** the board scan runs
- **THEN** the change status is `draft`

#### Scenario: Todo status
- **GIVEN** a change has tasks and zero completed checklist items
- **WHEN** the board scan runs
- **THEN** the change status is `todo`

#### Scenario: In-progress status
- **GIVEN** a change has both completed and incomplete checklist items
- **WHEN** the board scan runs
- **THEN** the change status is `in_progress`

#### Scenario: Done status
- **GIVEN** a change has tasks and every checklist item is complete
- **WHEN** the board scan runs
- **THEN** the change status is `done`

#### Scenario: Archived status
- **GIVEN** a change lives under `openspec/changes/archive/`
- **WHEN** the board scan runs
- **THEN** the change status is `archived` regardless of task completion

### Requirement: Change detail API
The dashboard API SHALL expose full detail for a selected change.

#### Scenario: Existing change detail
- **GIVEN** a selected source contains the requested change
- **WHEN** the dashboard requests change detail
- **THEN** the API returns the change name, title, status, archive flag, task stats, proposal markdown, design markdown, tasks markdown, and delta spec entries

#### Scenario: Delta spec comparison
- **GIVEN** a change contains delta spec files under its `specs/` directory
- **WHEN** the API returns change detail
- **THEN** each delta spec entry includes relative path, proposed content, current worktree spec content when present, status, and a unified diff when content changed

#### Scenario: Missing change detail
- **WHEN** the dashboard requests a change that does not exist in the selected source
- **THEN** the API returns a not-found response

### Requirement: Idea detail API
The dashboard API SHALL expose full markdown detail for selected idea files.

#### Scenario: Existing idea detail
- **GIVEN** an idea markdown file exists under `openspec/ideas/`
- **WHEN** the dashboard requests idea detail
- **THEN** the API returns the idea name, title, ideas status, and markdown content

#### Scenario: Missing idea detail
- **WHEN** the dashboard requests an idea that does not exist
- **THEN** the API returns a not-found response

### Requirement: Board user interface
The dashboard UI SHALL render changes and ideas in status-oriented columns and let maintainers inspect one selected artifact at a time.

#### Scenario: Board columns
- **WHEN** the dashboard renders an initialized source
- **THEN** it displays ideas, draft, todo, in-progress, done, and archived groups using the source scan payload

#### Scenario: Artifact selection
- **WHEN** the user selects a change or idea card
- **THEN** the dashboard opens a focused detail panel for that artifact rather than requiring the user to navigate away

#### Scenario: Change artifact tabs
- **GIVEN** a selected change includes proposal, tasks, design, or spec deltas
- **WHEN** the detail panel renders
- **THEN** the user can switch among those artifact views and see missing artifacts clearly

### Requirement: Markdown and task rendering
The dashboard UI SHALL render OpenSpec markdown and tasks in readable HTML while keeping the plugin self-contained.

#### Scenario: Markdown display
- **WHEN** proposal, design, idea, or spec markdown is displayed
- **THEN** the UI renders common markdown elements including headings, bold text, inline code, lists, horizontal rules, and paragraphs

#### Scenario: Task checklist display
- **WHEN** a tasks document contains OpenSpec checklist items
- **THEN** the UI displays task structure and completion status in a parsed, readable form instead of raw undifferentiated markdown

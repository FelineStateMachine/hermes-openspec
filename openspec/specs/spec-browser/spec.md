# Spec Browser and Diff View

## Purpose

The dashboard plugin SHALL provide a spec browser for current OpenSpec specs and diffs across working tree and git refs. The browser must help maintainers inspect requirements, scenarios, metadata, and changes without reading raw markdown unless they choose to.

## Requirements

### Requirement: Current spec browser mode
The dashboard API SHALL return the current worktree spec set for an initialized source when no diff parameters are requested.

#### Scenario: List current specs
- **GIVEN** markdown specs exist under `openspec/specs/`
- **WHEN** the dashboard requests the spec browser without before/after refs and without dirty mode
- **THEN** the API returns mode `current`, current branch, each spec path, token, title, status `current`, content, and changed flag `false`

#### Scenario: Current spec timestamps
- **GIVEN** git history or filesystem metadata is available for a current spec
- **WHEN** the API returns current spec browser entries
- **THEN** each entry includes most-recent edit time when available and creation time when git history can determine it

### Requirement: Dirty worktree diff mode
The dashboard API SHALL compare a git ref to current worktree specs when dirty mode is requested.

#### Scenario: Dirty diff defaults
- **WHEN** dirty mode is requested without an explicit before ref
- **THEN** the API compares `HEAD` to the working tree

#### Scenario: Dirty diff filters unchanged specs
- **GIVEN** some specs match the selected before ref exactly
- **WHEN** dirty mode is requested
- **THEN** unchanged specs are omitted from the returned files list

#### Scenario: Dirty diff entry
- **GIVEN** a spec was added, modified, or deleted relative to the before ref
- **WHEN** dirty mode is requested
- **THEN** the API returns before content, after content, status, changed flag, unified diff, and available timestamps for that spec

### Requirement: Ref-to-ref diff mode
The dashboard API SHALL compare specs between two explicit git refs when both before and after refs are supplied.

#### Scenario: Valid ref comparison
- **GIVEN** both before and after refs are supplied
- **WHEN** the dashboard requests the spec browser
- **THEN** the API returns mode `refs`, both labels, all spec paths present in either ref, per-spec status, before content, after content, changed flag, and unified diff when changed

#### Scenario: Incomplete ref comparison
- **WHEN** only one of before or after is supplied outside dirty mode
- **THEN** the API rejects the request with a 400-level error explaining that both refs are required

### Requirement: Safe spec path handling
The API SHALL prevent spec detail and git content reads from escaping `openspec/specs/`.

#### Scenario: Worktree spec path traversal
- **WHEN** a spec detail request contains an absolute path or parent-directory traversal outside the specs root
- **THEN** the API returns not found and does not read outside the specs directory

#### Scenario: Ref spec path traversal
- **WHEN** a git-ref spec read is requested for an absolute path or a path containing `..`
- **THEN** the API returns no content and does not invoke git with an escaped specs path

### Requirement: Spec detail API
The dashboard API SHALL expose the content of a selected current spec.

#### Scenario: Existing spec detail
- **GIVEN** a requested spec path exists under `openspec/specs/`
- **WHEN** the dashboard requests spec detail
- **THEN** the API returns the path, title, and markdown content

#### Scenario: Missing spec detail
- **WHEN** the dashboard requests a spec path that does not exist under `openspec/specs/`
- **THEN** the API returns a not-found response

### Requirement: Structured requirement display
The dashboard UI SHALL render OpenSpec requirements and scenarios as structured content in spec and diff views when the format is recognized.

#### Scenario: Requirement section parsing
- **GIVEN** spec content contains OpenSpec requirement headings and scenario headings
- **WHEN** the UI renders the spec or diff view
- **THEN** it displays requirement names, requirement text, scenario names, and scenario bullets as structured elements instead of a raw markdown block

#### Scenario: Unknown markdown fallback
- **GIVEN** spec content does not match the recognized OpenSpec requirement format
- **WHEN** the UI renders the spec or diff view
- **THEN** it falls back to safe markdown rendering rather than hiding content

### Requirement: Copyable identifiers
The spec browser SHALL expose copyable identifiers for sources, changes, and specs that agents can resolve later.

#### Scenario: Copy spec token
- **GIVEN** a spec browser entry has a source name and spec token
- **WHEN** the user copies the identifier chip
- **THEN** the copied text is `<source-name>/<os_token>` and can be resolved by `openspec_context`

#### Scenario: Copy feedback
- **WHEN** a user copies an identifier chip
- **THEN** the UI gives brief visible feedback that the value was copied

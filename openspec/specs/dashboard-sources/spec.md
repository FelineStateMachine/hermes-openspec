# Dashboard Source Management

## Purpose

The dashboard plugin SHALL let maintainers register, inspect, initialize, update, and remove OpenSpec-capable repositories from the Hermes dashboard. Source management must work even before a repository has been initialized with an `openspec/` directory.

## Requirements

### Requirement: Source listing API
The dashboard API SHALL list registered sources with live validity, repository, and OpenSpec scan information.

#### Scenario: Valid initialized source
- **GIVEN** a registered source path resolves to a repository with an `openspec/` directory
- **WHEN** the dashboard requests the source list
- **THEN** the API returns the source as valid with repo root, OpenSpec path, scanned changes, scanned ideas, scanned specs, and status counts

#### Scenario: Existing but uninitialized source
- **GIVEN** a registered source path resolves to an existing repository without an `openspec/` directory
- **WHEN** the dashboard requests the source list
- **THEN** the API returns the source as invalid with the repo root and a `No openspec/ directory found` error

#### Scenario: Missing path
- **GIVEN** a registered source path no longer exists
- **WHEN** the dashboard requests the source list
- **THEN** the API returns the source as invalid with an explanatory error instead of dropping the source

### Requirement: Source path resolution
The dashboard API SHALL normalize user-provided paths and derive the repository root when possible.

#### Scenario: Path inside a git repository
- **GIVEN** a user submits a path inside a git repository
- **WHEN** the API registers or updates a source
- **THEN** it resolves the repository root for validation and payload metadata

#### Scenario: Non-git directory
- **GIVEN** a user submits an existing directory that is not inside a git repository
- **WHEN** the API registers or updates a source
- **THEN** it accepts that directory as the source root

#### Scenario: Invalid path input
- **WHEN** a user submits an empty path, null-byte path, unparseable path, or non-existent path
- **THEN** the API rejects the request with a 400-level error and does not modify the registry

### Requirement: Source CRUD operations
The dashboard API SHALL expose create, update, and delete operations for registry sources.

#### Scenario: Register source
- **WHEN** the dashboard submits a valid source path and optional display name
- **THEN** the API stores the source and returns the source payload with live validity metadata

#### Scenario: Update source
- **GIVEN** a registered source exists
- **WHEN** the dashboard submits a new valid path or name for that source
- **THEN** the API updates the registry and returns the refreshed source payload

#### Scenario: Duplicate path conflict
- **GIVEN** another source already uses a submitted path
- **WHEN** the dashboard creates or updates a source with that path
- **THEN** the API returns a conflict response and preserves the existing registry state

#### Scenario: Remove source
- **GIVEN** a registered source exists
- **WHEN** the dashboard deletes the source
- **THEN** the API removes it from the registry and subsequent source lists omit it

### Requirement: Source initialization
The dashboard API SHALL initialize a registered source that exists but lacks an `openspec/` directory.

#### Scenario: OpenSpec CLI available
- **GIVEN** the OpenSpec CLI binary is available
- **WHEN** the dashboard initializes an uninitialized source
- **THEN** the API runs `openspec init <repo-root> --tools none` and returns the refreshed source payload

#### Scenario: OpenSpec CLI unavailable
- **GIVEN** the OpenSpec CLI binary is unavailable
- **WHEN** the dashboard initializes an uninitialized source
- **THEN** the API creates a minimal `openspec/changes`, `openspec/specs`, and `openspec/ideas` directory structure and returns the refreshed source payload

#### Scenario: Already initialized source
- **GIVEN** the source already has an `openspec/` directory
- **WHEN** the dashboard initializes the source
- **THEN** the API returns success with an `Already initialized` message and does not modify existing artifacts

### Requirement: Dashboard source controls
The dashboard UI SHALL present compact controls for selecting and managing registered sources.

#### Scenario: Source selection
- **GIVEN** one or more registered sources exist
- **WHEN** the dashboard renders the OpenSpec tab
- **THEN** the user can select the active source from a top-level control and see invalid sources labelled as invalid

#### Scenario: Source actions
- **WHEN** the user opens source management controls
- **THEN** the user can refresh sources, add a source, edit the active source, remove the active source, and initialize an uninitialized active source when applicable

#### Scenario: Empty source list
- **GIVEN** no sources are registered
- **WHEN** the dashboard renders the OpenSpec tab
- **THEN** it shows an empty-state path to add a source instead of rendering a broken board

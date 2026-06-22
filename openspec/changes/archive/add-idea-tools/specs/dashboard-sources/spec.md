# Dashboard Source Management Delta

## MODIFIED Requirements

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

#### Scenario: Tool-created idea appears in scans
- **GIVEN** an agent creates an idea through `openspec_idea_create` under a registered source
- **WHEN** the dashboard source list or source detail scan is requested
- **THEN** the created idea appears in the scanned ideas list with its slug, title, source id, and `ideas` status

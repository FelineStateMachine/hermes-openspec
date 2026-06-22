## MODIFIED Requirements

### Requirement: Source initialization
The dashboard API SHALL initialize a registered source that exists but lacks an `openspec/` directory and SHALL normalize the resulting OpenSpec layout to include all directory roots used by the plugin.

#### Scenario: OpenSpec CLI available
- **GIVEN** the OpenSpec CLI binary is available
- **WHEN** the dashboard initializes an uninitialized source
- **THEN** the API runs `openspec init <repo-root> --tools none`, ensures `openspec/changes`, `openspec/changes/archive`, `openspec/specs`, and `openspec/ideas` all exist, and returns the refreshed source payload

#### Scenario: OpenSpec CLI unavailable
- **GIVEN** the OpenSpec CLI binary is unavailable
- **WHEN** the dashboard initializes an uninitialized source
- **THEN** the API creates `openspec/changes`, `openspec/changes/archive`, `openspec/specs`, and `openspec/ideas` and returns the refreshed source payload

#### Scenario: Already initialized source
- **GIVEN** the source already has an `openspec/` directory
- **WHEN** the dashboard initializes the source
- **THEN** the API returns success with an `Already initialized` message and does not modify existing artifacts

#### Scenario: CLI-listable initialized source
- **GIVEN** a source has been initialized through the dashboard API
- **WHEN** an agent or maintainer runs OpenSpec list commands in that source
- **THEN** the required OpenSpec directories exist so list operations are not blocked by a missing `changes` root

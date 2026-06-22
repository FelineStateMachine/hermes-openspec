# OpenSpec Source Registry

## Purpose

The plugin SHALL maintain a lightweight registry of repositories that the OpenSpec dashboard and agent tools can address by stable, copyable identifiers. The registry is intentionally separate from OpenSpec artifact storage: sources are stored in SQLite, while changes and specs are read live from each repository's filesystem.

## Requirements

### Requirement: Profile-local source storage
The registry SHALL store OpenSpec sources in the active Hermes home so each Hermes profile has an independent source list.

#### Scenario: Registry database path
- **WHEN** the registry opens its database
- **THEN** it uses `<hermes_home>/openspec.db` from Hermes' profile-aware home resolver

#### Scenario: Database initialization
- **WHEN** source data is first read or written
- **THEN** the registry creates the source table and unique path index if they do not already exist

### Requirement: Source record identity
Each registered source SHALL have a stable internal token, an optional vanity name, an absolute or user-expanded path string, and a creation timestamp.

#### Scenario: Add new source
- **GIVEN** a path is not already registered
- **WHEN** the registry adds the source
- **THEN** it generates an `os_` token, stores the source, and returns token/id aliases, name, path, and created_at

#### Scenario: Duplicate source path
- **GIVEN** a source path is already registered
- **WHEN** the registry attempts to add the same normalized path again
- **THEN** it rejects the operation with a duplicate-source error

#### Scenario: Update source
- **GIVEN** an existing source token
- **WHEN** the registry updates the source path or vanity name
- **THEN** it preserves the token and creation timestamp while replacing the path and name

#### Scenario: Remove source
- **GIVEN** an existing source token
- **WHEN** the registry removes the source
- **THEN** the source no longer appears in registry listings or identifier resolution

### Requirement: Human-facing source names
The registry SHALL resolve sources by explicit vanity name first and by path basename when no vanity name is set.

#### Scenario: Explicit vanity name
- **GIVEN** a source has a non-empty `name`
- **WHEN** an agent resolves that name case-insensitively
- **THEN** the registry returns the matching source

#### Scenario: Basename fallback
- **GIVEN** a source has no explicit `name`
- **WHEN** an agent resolves the basename of the source path case-insensitively
- **THEN** the registry returns the matching source

### Requirement: Deterministic artifact tokens
The registry SHALL derive copyable `os_` artifact tokens deterministically from change names and spec paths rather than storing per-artifact rows.

#### Scenario: Change token derivation
- **WHEN** a change folder name is converted into a token
- **THEN** the token is a stable `os_` value derived from the change name

#### Scenario: Spec token derivation
- **WHEN** a spec path is converted into a token
- **THEN** the token is a stable `os_` value derived from the `spec:<relative-path>` key

#### Scenario: Filesystem stays authoritative
- **GIVEN** a change or spec is renamed, added, archived, or removed on disk
- **WHEN** tools scan the repository
- **THEN** the current filesystem state determines which artifact tokens resolve

### Requirement: Legacy source migration
The registry SHALL support one-time migration from legacy dashboard configuration sources into the SQLite registry.

#### Scenario: Legacy sources exist
- **GIVEN** the Hermes dashboard config contains legacy OpenSpec source entries
- **WHEN** the plugin API lists registered sources for the first time in a process
- **THEN** it attempts to migrate those sources into the registry idempotently

#### Scenario: Legacy migration failure
- **WHEN** legacy source migration raises an exception
- **THEN** source listing continues using the SQLite registry without crashing the dashboard API

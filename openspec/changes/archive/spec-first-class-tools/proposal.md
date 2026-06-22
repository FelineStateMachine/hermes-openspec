## Why

Specs are the only core OpenSpec artifact without first-class agent tools. Changes have create→promote→archive. Ideas have create→enrich→promote. Specs require hand-writing markdown after calling `openspec_instructions(artifact=specs)` for the authoring guide — no structured create, no filesystem-backed read, no dedicated list. This blocks agents from programmatically creating and inspecting specs without the CLI binary.

## What Changes

- Add `openspec_spec_create` — structured input (title, purpose, requirements array with scenarios) → writes properly formatted `spec.md`. `change` param scopes to change delta specs; omitting it targets baseline specs.
- Add `openspec_spec_show` — reads a spec as structured JSON using the existing `spec_parser.parse_spec`. Works on both change and baseline specs. Filesystem-backed (no CLI needed).
- Add `openspec_spec_list` — lists specs within a change, or baseline specs. Filesystem-backed.
- Add `spec_to_markdown` serializer to `spec_parser.py` — inverse of `parse_spec`, converts structured input to `### Requirement:` / `#### Scenario:` format.

All three tools are filesystem-backed (always available, like idea/change tools). `spec_show` and `spec_list` reuse `spec_parser.py` from the semantic diff work.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `agent-tools`: Add spec lifecycle tools for create, show, and list workflows.

## Impact

- `spec_parser.py` — add `spec_to_markdown` serializer
- `schemas.py` — three new schemas
- `tools.py` — three new handlers
- `__init__.py` — register three new tools
- `plugin.yaml` — declare three new tools
- `README.md`, `docs/tool-reference.md` — tool count and table updates
- Tests for structured create, parse round-trip, overwrite protection, change vs baseline scoping, and listing

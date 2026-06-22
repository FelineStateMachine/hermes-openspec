## Context

The plugin already has two classes of agent tools: CLI-backed wrappers (`openspec_list`, `openspec_show`, `openspec_validate`, `openspec_status`, `openspec_instructions`) and filesystem-backed context resolution (`openspec_context`). Ideas are already part of the dashboard scan model under `openspec/ideas/`, but agents had no write-side primitive for capturing, enriching, or promoting ideas.

The new idea tools are filesystem-backed because OpenSpec CLI currently has no `openspec new idea` command. They still follow existing plugin conventions: JSON string responses, `ok: true/false`, explicit validation errors, `workdir` support, and registered-source identifier support where possible.

## Goals / Non-Goals

**Goals:**

- Create idea markdown files deterministically under `openspec/ideas/`.
- Let agents update a structured enrichment section without duplicating old reports.
- Promote reviewed ideas into valid OpenSpec change scaffolds that preserve traceability.
- Keep the tools usable even when the OpenSpec CLI binary is unavailable.
- Keep generated artifacts simple enough for humans to review and refine.

**Non-Goals:**

- Automatically spawning subagents from `openspec_idea_create`.
- Inferring final capability boundaries during promotion.
- Replacing human review before a promoted idea becomes implementation work.
- Adding dashboard write controls in this change.

## Decisions

### Filesystem-backed write tools

`openspec_idea_create`, `openspec_idea_enrich`, `openspec_idea_promote`, and the task/change lifecycle tools write repo-local markdown directly instead of calling the OpenSpec CLI.

Alternative considered: shell out to hypothetical CLI commands. Rejected because the current OpenSpec CLI exposes `openspec new change`, not `openspec new idea`, and direct filesystem writes match the existing dashboard scan contract.

### Explicit lifecycle steps

Creation, enrichment, and promotion are separate tools. Creation does not automatically enrich or promote.

Alternative considered: one orchestration tool that creates and enriches in a single call. Rejected because agent/human orchestration needs pause points for review and feedback.

### Deterministic slugging and collision suffixes

Idea file names are safe slugs derived from title or an explicit slug. Collisions append `-2`, `-3`, etc. rather than overwriting.

Alternative considered: timestamps in every slug. Rejected because deterministic human-readable names are easier to inspect and copy.

### Replaceable enrichment block

Enrichment uses sentinel comments around a single `## Enrichment Report` block. Re-enriching replaces that block instead of appending duplicates.

Alternative considered: append every enrichment as history. Rejected for now because the first workflow needs the current report more than audit history.

### Promotion creates a valid placeholder spec delta

Promoted ideas create proposal, tasks, metadata, and a placeholder `specs/<change>/spec.md` delta. The placeholder is valid OpenSpec and explicitly says it must be refined before implementation.

Alternative considered: proposal/tasks only. Rejected because strict OpenSpec validation requires at least one delta, and generated scaffolds should validate immediately.

## Risks / Trade-offs

- Placeholder specs can be mistaken for final requirements → Mitigation: wording says they must be refined before implementation.
- Direct filesystem writes bypass future CLI validation rules → Mitigation: outputs are covered by tests and strict OpenSpec validation.
- Registered-source resolution depends on registry availability → Mitigation: explicit `workdir` remains the primary and simplest path.
- Enrichment replacement discards prior report history → Mitigation: acceptable for the first version; history can be added later if needed.

## Migration Plan

- Existing OpenSpec repos need no migration.
- New tools create missing `openspec/changes`, `openspec/changes/archive`, `openspec/specs`, and `openspec/ideas` roots as needed.
- Deployment is a normal plugin update/reload; no database migration is required.

## Open Questions

- Whether future dashboard UI should expose create/enrich/promote actions directly.
- Whether enrichment should eventually support durable history instead of one replaceable current report.
- Whether promotion should accept explicit capability names once human review has selected affected specs.

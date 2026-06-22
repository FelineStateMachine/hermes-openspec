## 1. Tool Contracts

- [x] 1.1 Rename idea tools to `openspec_idea_create`, `openspec_idea_enrich`, and `openspec_idea_promote`.
- [x] 1.2 Define schemas for task lifecycle tools: `openspec_task_list` and `openspec_task_set_status`.
- [x] 1.3 Define schemas for change lifecycle tools: `openspec_change_create`, `openspec_change_promote`, `openspec_change_archive`, and `openspec_change_unarchive`.
- [x] 1.4 Register the uniform noun-action tool surface in the plugin manifest and Python registration layer.

## 2. Idea Lifecycle

- [x] 2.1 Implement source/workdir resolution and `openspec/ideas/` layout creation for idea writes.
- [x] 2.2 Implement safe idea markdown generation from title, prompt, origin/source, tags, and optional notes.
- [x] 2.3 Implement idea enrichment report writing/updating.
- [x] 2.4 Implement idea promotion to a valid change scaffold with source traceability.
- [x] 2.5 Add regression tests for idea creation, slug collision handling, enrichment replacement, promotion validation, and old-name removal.

## 3. Task Lifecycle

- [x] 3.1 Implement checklist parsing for ordered task ids, text, status, and aggregate counts.
- [x] 3.2 Implement status updates for selected task ids with `todo` and `done` states.
- [x] 3.3 Return refreshed derived change status after task updates.
- [x] 3.4 Add tests for task listing, status updates, missing task errors, and no-accidental-edit behavior.

## 4. Change Lifecycle

- [x] 4.1 Implement direct change creation with proposal, optional tasks, metadata, and optional placeholder spec delta.
- [x] 4.2 Implement change promotion from draft to todo by ensuring tasks and a valid spec delta exist.
- [x] 4.3 Implement archive of completed changes with incomplete-task refusal unless forced.
- [x] 4.4 Implement unarchive with active-change collision refusal unless forced.
- [x] 4.5 Add tests for change creation, promotion, archive/unarchive, collision refusal, and strict validation of generated scaffolds.

## 5. Documentation and Verification

- [x] 5.1 Update README tool surface documentation.
- [x] 5.2 Run Python syntax checks for modified plugin files.
- [x] 5.3 Run targeted and full pytest suites.
- [x] 5.4 Run `openspec validate --all --strict --json --no-interactive`.

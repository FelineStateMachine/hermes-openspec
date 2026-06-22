## Why

Agents and humans can currently read OpenSpec artifacts, but they need a uniform write-side lifecycle surface to capture ideas, enrich them, create/promote changes, move task work toward done, and archive/unarchive completed work without manually editing files. A noun-action tool naming convention makes this surface easier for agents and humans to discover and use consistently.

## What Changes

- Rename the idea lifecycle tools to noun-action names:
  - `openspec_idea_create`
  - `openspec_idea_enrich`
  - `openspec_idea_promote`
- Add task lifecycle tools:
  - `openspec_task_list`
  - `openspec_task_set_status`
- Add change lifecycle tools:
  - `openspec_change_create`
  - `openspec_change_promote`
  - `openspec_change_archive`
  - `openspec_change_unarchive`
- Keep lifecycle operations explicit: creating ideas, enriching ideas, promoting ideas, creating changes, promoting changes, updating tasks, and archiving/unarchiving changes remain separate reviewable steps.
- Use deterministic filesystem behavior, safe slug/change-id generation, collision handling, and structured JSON responses so agents can chain the tools reliably.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `agent-tools`: Add write-side idea, task, and change lifecycle tools using uniform noun-action naming.
- `dashboard-sources`: Ensure dashboard/source scans can reflect ideas and changes created or moved by agent tools without extra manual refresh assumptions.

## Impact

- Affected tool registration and schemas:
  - `plugin.yaml`
  - `__init__.py`
  - `schemas.py`
  - `tools.py`
- Affected OpenSpec filesystem conventions:
  - `openspec/ideas/<slug>.md`
  - `openspec/changes/<change-id>/proposal.md`
  - `openspec/changes/<change-id>/tasks.md`
  - `openspec/changes/<change-id>/specs/**/spec.md`
  - `openspec/changes/archive/<change-id>/`
- Affected dashboard behavior only insofar as tool-created and tool-moved artifacts must appear in existing source scans.
- Tests should cover naming exposure, slug/collision handling, invalid workdirs, idea creation/enrichment/promotion, change creation/promotion/archive/unarchive, task listing/status updates, validation of promoted scaffolds, and refusal to overwrite existing artifacts unless explicitly allowed.

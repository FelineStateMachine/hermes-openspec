## Context

The plugin wraps the upstream OpenSpec CLI, but the CLI currently has two behaviors that are awkward for the Hermes plugin UX:

- `openspec init --tools none` does not create every directory the plugin supports (`ideas/` in particular).
- `openspec instructions` requires at least one change even when the requested artifact guidance can be derived from schema templates.

The plugin should not fork OpenSpec behavior, but it can normalize its own integration boundaries so dashboard and agent workflows are predictable.

## Goals / Non-Goals

**Goals:**

- Make dashboard-initialized repos immediately compatible with plugin scans and normal OpenSpec list commands.
- Keep fallback initialization and CLI-backed initialization producing the same directory layout.
- Let agents request spec-writing guidance in a fresh repository without first creating a dummy change.
- Preserve raw CLI command behavior wherever the CLI successfully returns useful output.

**Non-Goals:**

- Change the upstream OpenSpec CLI.
- Add a new agent tool for initialization.
- Invent a full replacement for `openspec instructions`.

## Decisions

- Add a local `_ensure_openspec_layout(root)` helper in the dashboard API and call it after both CLI init and fallback init.
- Keep `.gitkeep` files out of runtime init paths; create directories only. Repo-local `.gitkeep` files are only for versioning empty directories in this plugin repository.
- Normalize only the high-confidence artifact alias `spec -> specs`.
- If `openspec instructions` fails because no changes exist, call `openspec templates --json`, read the requested artifact template, and return it as structured fallback stdout while preserving the original reason.

## Risks / Trade-offs

- Template fallback is less rich than CLI enriched instructions tied to a concrete change. The response explicitly marks `fallback: template` so callers know the difference.
- Fallback depends on the OpenSpec CLI's `templates --json` output. If that output changes, the regression test should catch the break.

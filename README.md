# hermes-openspec

OpenSpec integration plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent) — spec-driven development tools and a dashboard tab for browsing change proposals, specs, and branch diffs across registered repos.

## Why this exists

OpenSpec keeps spec files (`openspec/changes/`, `openspec/specs/`, `openspec/ideas/`) inside the repo alongside code. But there's no way to browse those specs from the Hermes dashboard, and the agent has no native tools to resolve OpenSpec identifiers or run OpenSpec CLI commands.

This plugin closes both gaps:

- **Agent tools** — tools to resolve OpenSpec identifiers, run OpenSpec CLI workflows, and manage idea lifecycle artifacts without shelling out manually. CLI-backed tools are gated behind the OpenSpec binary's availability; filesystem-backed context/idea tools remain available without the CLI.
- **Dashboard tab** — a `/openspec` tab in the Hermes dashboard where you register repos, drill into change proposals (tasks, designs, specs, deltas), browse current specs, and compare branch diffs — all without leaving the dashboard.

## What you get

**Agent tools** — 20 tools covering the full OpenSpec lifecycle: idea capture and enrichment, change creation/promotion/archival, task tracking, spec validation, semantic spec diffing, spec create/show/list, context resolution, and a CLI passthrough (`openspec_cli`).

| Group | Tools |
|---|---|
| Context & reads | `openspec_context`, `openspec_list`, `openspec_show`, `openspec_status`, `openspec_validate`, `openspec_instructions` |
| Ideas | `openspec_idea_create`, `openspec_idea_enrich`, `openspec_idea_promote` |
| Changes | `openspec_change_create`, `openspec_change_promote`, `openspec_change_archive`, `openspec_change_unarchive` |
| Tasks | `openspec_task_list`, `openspec_task_set_status` |
| Specs | `openspec_spec_diff`, `openspec_spec_create`, `openspec_spec_show`, `openspec_spec_list` |
| CLI passthrough | `openspec_cli` |

`openspec_context`, `openspec_spec_diff`, `openspec_spec_create`, `openspec_spec_show`, `openspec_spec_list`, and the lifecycle write tools (idea/change/task) are filesystem-backed and always available. `openspec_list`, `openspec_show`, `openspec_validate`, `openspec_status`, and `openspec_instructions` require the `openspec` CLI binary.

For the full tool reference, lifecycle states, and delegation patterns, see [docs/index.md](docs/index.md).

**Bundled skills** — 11 upstream OpenSpec workflow skills (`openspec-propose`, `openspec-apply-change`, `openspec-verify-change`, etc.) are bundled and auto-registered. The agent loads them when user intent matches (e.g. "propose a change for dark mode" → `openspec-propose`). Skills instruct the agent to run the `openspec` CLI directly — they don't use the plugin's tool wrappers. See [docs/layers.md](docs/layers.md) for the layer architecture.

**Dashboard tab** (`/openspec`):

- Register repos by path — each gets a vanity name and stable tokens (`name/os_a1b2c3`).
- **Changes view** — Kanban-style board: ideas → draft → todo → in_progress → done → archived. Click any change to read its proposal, tasks, design, and spec deltas. Spec deltas render side-by-side (current vs proposed) with structured requirement/scenario parsing.
- **Specs view** — browse current specs in the worktree, sorted alphabetically or by last git commit date. Compare against HEAD (dirty mode) or arbitrary git refs (before/after).
- **Source initialization** — register a repo before it has an `openspec/` directory, then initialize it from the dashboard. CLI-backed and fallback initialization both normalize the plugin-supported layout: `openspec/changes/`, `openspec/changes/archive/`, `openspec/specs/`, and `openspec/ideas/`.
- Deep-linking via URL hash (`#project-name/token#anchor` — the second `#` selects a tab: proposal, tasks, design, or specs).

![Change board](screenshots/board.png)

![Spec browser](screenshots/specs.png)

## Requirements

- **Hermes Agent** — any recent build that supports the plugin system (`hermes plugins install`).
- **OpenSpec CLI** (optional) — needed for CLI-backed agent tools: list, show, validate, status, and instructions. The dashboard tab and filesystem-backed context/idea tools work without it. Install via `npm install -g @fission-ai/openspec@latest` or set `OPENSPEC_BIN` to the binary path.
- **Git** — used for branch diffs and spec commit-date sorting.

## Quickstart

```bash
# Install the plugin
hermes plugins install FelineStateMachine/hermes-openspec

# Enable it (prompts automatically during install, or run explicitly)
hermes plugins enable openspec
```

Restart Hermes if it's running. The OpenSpec tab appears in the dashboard at `/openspec`.

To register a repo in the dashboard, open the OpenSpec tab and click **Add source**, or use the agent tool:

```
openspec_context(identifier="/path/to/your/repo")
```

The repo doesn't need an `openspec/` directory upfront — if it's missing, the dashboard shows an **Initialize** button that creates the plugin-supported OpenSpec roots. Once initialized, the dashboard shows changes, ideas, and specs live from the filesystem.

## Verify

```bash
# Confirm the plugin is installed and enabled
hermes plugins list --plain

# Check that the openspec binary is found
openspec --version

# In the dashboard, open the OpenSpec tab
# (or curl the API if the dashboard is running on loopback)
curl http://127.0.0.1:9119/api/plugins/openspec/sources
```

If `openspec` isn't on your PATH, set `OPENSPEC_BIN`:

```bash
export OPENSPEC_BIN=/home/user/.npm-global/bin/openspec
```

## Update

```bash
hermes plugins update openspec
```

This pulls the latest from the remote and reloads. If the backend API routes changed (`plugin_api.py`), restart Hermes to remount them — the dashboard rescan (`/api/dashboard/plugins/rescan`) reloads frontend assets but does not remount backend routes.

## Documentation map

```
hermes-openspec/
├── plugin.yaml              # Tool plugin manifest — declares agent tools
├── __init__.py              # Plugin registration — wires tools, sets check_fn gating
├── schemas.py               # Tool parameter schemas (JSON Schema for each tool)
├── tools.py                 # Tool handlers — wraps OpenSpec CLI and filesystem-backed idea workflows
├── registry.py              # SQLite registry of sources at <hermes_home>/openspec.db
├── dashboard/
│   ├── manifest.json        # Dashboard tab manifest — tab path, position, entry/css/api
│   ├── plugin_api.py        # FastAPI router mounted at /api/plugins/openspec/
│   └── dist/
│       ├── index.js         # Dashboard tab frontend (IIFE, uses Hermes plugin SDK)
│       └── style.css        # Plugin styles (uses dashboard --color-* tokens)
```

| File | What to read it for |
|---|---|
| `plugin.yaml` | Which tools the plugin provides |
| `tools.py` | Tool handlers for CLI-backed commands and filesystem-backed idea workflows |
| `registry.py` | Source registry schema, token derivation, DB path |
| `dashboard/plugin_api.py` | All backend API routes and the spec-browser logic |
| `dashboard/manifest.json` | Tab registration, entry points |
| `dashboard/dist/index.js` | Frontend: board, specs view, source dialogs, deep-linking |

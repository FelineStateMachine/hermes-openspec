# hermes-openspec

OpenSpec integration plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent) — spec-driven development tools and a dashboard tab for browsing change proposals, specs, and branch diffs across registered repos.

## Why this exists

OpenSpec keeps spec files (`openspec/changes/`, `openspec/specs/`, `openspec/ideas/`) inside the repo alongside code. But there's no way to browse those specs from the Hermes dashboard, and the agent has no native tools to resolve OpenSpec identifiers or run OpenSpec CLI commands.

This plugin closes both gaps:

- **Agent tools** — six tools that wrap the `openspec` CLI so the agent can list, read, validate, and track OpenSpec changes and specs without shelling out manually. The tools are gated behind the CLI binary's availability, so they stay invisible if OpenSpec isn't installed.
- **Dashboard tab** — a `/openspec` tab in the Hermes dashboard where you register repos, drill into change proposals (tasks, designs, specs, deltas), browse current specs, and compare branch diffs — all without leaving the dashboard.

## What you get

**Agent tools** (gated on `openspec` binary):

| Tool | Does |
|---|---|
| `openspec_context` | Resolve a copyable `os_*` identifier (e.g. `puzzletea/os_a1b2c3`) into repo path + change/spec content. Entry point — call this first. |
| `openspec_list` | List changes or specs in a project, sorted by recent or name. |
| `openspec_show` | Show a change or spec as JSON — proposals, tasks, designs, deltas, requirements. |
| `openspec_validate` | Validate OpenSpec changes or specs in a project. |
| `openspec_status` | Show artifact completion status for a change (turns into kanban updates). |
| `openspec_instructions` | Enriched instructions for creating artifacts or applying tasks. |

`openspec_context` is always available (reads the registry DB + files only); the other five require the `openspec` CLI binary.

**Dashboard tab** (`/openspec`):

- Register repos by path — each gets a vanity name and stable tokens (`name/os_a1b2c3`).
- **Changes view** — Kanban-style board: ideas → draft → todo → in_progress → done → archived. Click any change to read its proposal, tasks, design, and spec deltas.
- **Specs view** — browse current specs in the worktree, sorted alphabetically or by last git commit date. Compare against HEAD (dirty mode) or arbitrary git refs (before/after).
- Deep-linking via URL hash (`#project-name/token`).

## Requirements

- **Hermes Agent** — any recent build that supports the plugin system (`hermes plugins install`).
- **OpenSpec CLI** (optional) — needed for five of the six agent tools. The dashboard tab works without it. Install via `npm install -g @fission-ai/openspec@latest` or set `OPENSPEC_BIN` to the binary path.
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

The repo needs an `openspec/` directory. Once registered, the dashboard shows changes and specs live from the filesystem.

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
├── plugin.yaml              # Tool plugin manifest — declares the six agent tools
├── __init__.py              # Plugin registration — wires tools, sets check_fn gating
├── schemas.py               # Tool parameter schemas (JSON Schema for each tool)
├── tools.py                 # Tool handlers — wraps the openspec CLI binary
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
| `tools.py` | How CLI commands are wrapped and how the binary is resolved |
| `registry.py` | Source registry schema, token derivation, DB path |
| `dashboard/plugin_api.py` | All backend API routes and the spec-browser logic |
| `dashboard/manifest.json` | Tab registration, entry points |
| `dashboard/dist/index.js` | Frontend: board, specs view, source dialogs, deep-linking |
```

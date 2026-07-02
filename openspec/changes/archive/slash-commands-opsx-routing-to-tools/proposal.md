# Slash commands /opsx:* routing to tools

## Summary

Implement the upstream OpenSpec `/opsx:*` command set (core + expanded profiles) as Hermes plugin slash commands. 11 commands route to the plugin's existing tool handlers via `ctx.dispatch_tool()`, providing power-user shortcuts for common spec-driven workflows.

## Motivation

The plugin registers 19 agent tools but no slash commands. Users who know what they want must either type a natural language prompt and let the agent select the right tool, or manually construct tool arguments. The upstream OpenSpec CLI defines a standard `/opsx:*` command set (`docs/commands.md`) that provides a canonical command surface. Implementing these as Hermes plugin slash commands gives users a familiar, fast shortcut.

## Design

### Command set

**Core profile (default):**
| Command | Routes to |
|---|---|
| `/opsx:propose` | `openspec_change_create` + `openspec_instructions(proposal)` |
| `/opsx:explore` | `openspec_idea_create` |
| `/opsx:apply` | `openspec_task_list` + `openspec_instructions(apply)` |
| `/opsx:archive` | `openspec_validate` → `openspec_change_archive` |

**Expanded workflow:**
| Command | Routes to |
|---|---|
| `/opsx:new` | `openspec_change_create` |
| `/opsx:continue` | `openspec_status` + `openspec_instructions(next_artifact)` |
| `/opsx:ff` | `openspec_change_create` → `openspec_change_promote` |
| `/opsx:verify` | `openspec_validate` + `openspec_status` + `openspec_task_list` |
| `/opsx:sync` | `openspec_spec_list` + `openspec_spec_diff` per spec |
| `/opsx:bulk-archive` | `openspec_change_archive` × N |
| `/opsx:onboard` | Static help text (no tool calls) |

All commands accept `--workdir <path>` or `--project <name>` flags to target a repo. Without flags, the current working directory is used.

### Implementation

Create `commands.py` with:
- `_parse_target(raw_args)` — extracts `--workdir`/`--project` flags, returns `(tool_args, positional_text)`
- `_dispatch(ctx, tool_name, args)` — calls `ctx.dispatch_tool()` and parses JSON result
- `_fmt_result(result, ok_label, error_label)` — formats tool result for display
- Per-command handlers that orchestrate 1-3 tool calls each
- `register_commands(ctx)` — loops over the command table and calls `ctx.register_command()`

Wire in `__init__.py` `register()` by calling `_commands.register_commands(ctx)` after tool registration.

### Confirmed API

- `ctx.register_command(name, handler, description, args_hint)` — accepts colon-delimited names (e.g. `"opsx:propose"`). The name is cleaned via `.lower().strip().lstrip("/")` — colons pass through.
- Command lookup in `cli.py` and `gateway/run.py` uses the full name including colon.
- `ctx.dispatch_tool(tool_name, args)` routes through the normal approval/redaction pipeline.
- No conflicts with built-in commands (checked via `resolve_command()`).

## Alternatives considered

- **Inject as user messages for the agent to handle.** Rejected — that's just a shortcut to typing the tool name. Direct routing is faster and doesn't consume tokens.
- **Call tools.py handlers directly (bypass dispatch_tool).** Rejected — `dispatch_tool` is the documented pattern and routes through approvals/redaction. Direct calls would bypass safety pipelines.

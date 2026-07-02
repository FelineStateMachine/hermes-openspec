## Context

The plugin registers 19 agent tools but no slash commands. The upstream OpenSpec CLI defines a standard `/opsx:*` command set (`docs/commands.md`) with two profiles: core (4 commands) and expanded (7 commands). Hermes plugins can register slash commands via `ctx.register_command(name, handler, description, args_hint)` — confirmed in `hermes_cli/plugins.py` and the build-a-plugin guide. Colon-delimited names work: the name cleaner does `.lower().strip().lstrip("/")`, colons pass through. Command lookup in `cli.py` and `gateway/run.py` uses the full name including colon.

`ctx.dispatch_tool(tool_name, args)` routes through the normal approval/redaction pipeline — it's the documented pattern for slash commands that invoke tools.

The existing tool handlers in `tools.py` all accept `(args: dict, **kwargs) -> str` and return JSON strings. The `__init__.py` `register()` function currently registers tools only.

## Goals / Non-Goals

**Goals:**
- Implement all 11 upstream `/opsx:*` commands as Hermes plugin slash commands
- Route to existing tool handlers via `ctx.dispatch_tool()` — no new tools, no new backend logic
- Support `--workdir` and `--project` flags for repo targeting on all commands
- Commands work in both CLI and gateway (Discord, Telegram)

**Non-Goals:**
- LLM-driven implementation (upstream `/opsx:apply` does implementation — our version lists tasks + returns instructions, it doesn't write code)
- Semantic analysis (upstream `/opsx:verify` does LLM analysis — our version runs `openspec_validate` + `openspec_status` + `openspec_task_list` and reports results)
- Auto-syncing delta specs into main specs (upstream `/opsx:sync` merges — our version shows diffs for manual review)
- Command-specific UI or formatting beyond plain text with emojis

## Decisions

### Decision 1: New `commands.py` module (not inline in `__init__.py`)

**Choice:** Create a dedicated `commands.py` module with all command handlers and a `register_commands(ctx)` function. Wire it in `__init__.py` with a single call.

**Why not inline:** 11 handlers + shared helpers (~300 lines) would bloat `__init__.py` (currently 68 lines, purely registration). A separate module keeps registration clean and makes the command layer testable in isolation.

**Why not in `tools.py`:** `tools.py` is for agent tool handlers (called by the model). Slash commands are user-invoked shortcuts that orchestrate tool calls. Different audience, different lifecycle.

### Decision 2: `ctx.dispatch_tool()` for all tool invocations

**Choice:** All commands call `ctx.dispatch_tool("openspec_*", args)` to invoke tools. No direct calls to `tools.py` handler functions.

**Why:** `dispatch_tool` is the documented pattern. It routes through the approval, redaction, and budget pipelines — the command gets the same safety treatment as a model-initiated tool call. Direct handler calls would bypass this.

**Trade-off:** `dispatch_tool` returns a string (the handler's JSON return). Commands parse it with `json.loads()` to extract fields for formatting. If parsing fails, the raw string is shown.

### Decision 3: Shared arg parsing via `_parse_target()`

**Choice:** A single `_parse_target(raw_args)` helper extracts `--workdir`/`--project` flags from the raw args string and returns `(tool_args, positional_text)`.

```
/opsx:propose add-dark-mode --workdir ~/repos/my-project
  → tool_args = {"workdir": "~/repos/my-project"}
  → positional = "add-dark-mode"
```

```
/opsx:propose add-dark-mode --project hermes-openspec
  → tool_args = {"identifier": "hermes-openspec"}
  → positional = "add-dark-mode"
```

```
/opsx:propose add-dark-mode
  → tool_args = {}
  → positional = "add-dark-mode"
  (tools.py _resolve_project falls back to cwd when neither workdir nor identifier is set)
```

**Why shlex.split:** Handles quoted arguments (`/opsx:explore "add dark mode"`) correctly. Falls back to `raw_args.split()` if shlex fails (unbalanced quotes).

### Decision 4: Command handler closure pattern

**Choice:** Register handlers with a lambda closure that captures `ctx`:

```python
ctx.register_command(
    "opsx:propose",
    handler=lambda raw, h=_handle_propose, c=ctx: h(c, raw),
    description="Create change + get proposal instructions",
    args_hint="<change-name>",
)
```

**Why:** `ctx.register_command` expects `handler(raw_args: str) -> str | None`. The handlers need `ctx` for `dispatch_tool`. The closure captures `ctx` at registration time. This matches the pattern in the build-a-plugin guide.

### Decision 5: Multi-step commands report per-step results

**Choice:** Commands that dispatch multiple tools (propose, ff, verify, archive, sync, bulk-archive) report each step's result sequentially:

```
✅ Change 'add-dark-mode' created
  change_path: /home/tank/repos/my-project/openspec/changes/add-dark-mode

📋 Proposal authoring instructions:
...

Next: author proposal.md, then /opsx:ff add-dark-mode to fast-forward.
```

**Why not just the final result:** Multi-step commands can partially fail (e.g., change created but promotion failed). Per-step reporting tells the user exactly where it stopped.

### Decision 6: `/opsx:continue` next-artifact logic

**Choice:** A `_next_artifact(status_result)` helper inspects the `openspec_status` output and returns the next missing artifact in dependency order: proposal → design → specs → tasks. If all exist, returns `None` and the command tells the user to `/opsx:apply`.

**Why dependency order:** Matches the upstream artifact graph (proposal → specs/design → tasks → apply). The orchestrator should author artifacts in this order.

**Edge case:** `openspec_status` output shape varies between CLI-backed and filesystem-backed calls. The helper checks for both the nested dict format (`{"proposal": {"exists": true}}`) and the flat format (`{"hasProposal": true}`). If neither matches, defaults to "proposal".

### Decision 7: `/opsx:onboard` is static text

**Choice:** `/opsx:onboard` returns a static help string with the command list, typical workflow, and flag documentation. No tool calls.

**Why:** Onboarding is documentation, not a tool operation. Static text is instant and doesn't consume tool budget.

## Risks / Trade-offs

- **Partial failure in multi-step commands** → `/opsx:ff` creates then promotes. If create succeeds but promote fails, the change exists but isn't promoted. Mitigated: per-step reporting (Decision 5) makes the failure point clear. The user can re-run `/opsx:ff` (create will report "may already exist") or call `/opsx:continue` to proceed manually.

- **`dispatch_tool` inherits session approval mode** → In `smart` approval mode, `/opsx:archive` might auto-approve the archive tool call without prompting. This is the documented behavior — commands go through the same pipeline as model tool calls. Not a bug, but worth noting in the onboard text.

- **Colon command names in Telegram** → Telegram's bot menu uses underscores for autocomplete (`/opsx_propose`). The gateway normalizes underscores to hyphens (`command.replace("_", "-")`), but colons may not be normalized. Need to verify that `/opsx:propose` works in Telegram/Discord, or if the colon gets mangled. If it does, register underscored aliases (`opsx_propose`) as fallbacks.

- **`/opsx:continue` status shape ambiguity** → The `_next_artifact` helper handles two output formats but could encounter a third if the CLI changes. Mitigated: defaulting to "proposal" is safe (worst case: user gets proposal instructions when they already have one — they'll see it exists and skip).

## Open Questions

- Does Telegram's command parser handle colons in `/opsx:propose`? The `get_command()` method in `gateway/platforms/base.py` splits on space and strips the `/` — it doesn't reject colons. But Telegram's autocomplete menu may not surface colon-delimited commands. Need to test in a live Telegram session. If broken, register both `opsx:propose` and `opsx_propose` as aliases.

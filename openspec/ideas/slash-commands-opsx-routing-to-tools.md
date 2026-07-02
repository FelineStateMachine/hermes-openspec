# Slash commands /opsx:* routing to tools

## Source
- Origin: human
- Created: 2026-06-23T01:37:48Z
- Tags: slash-commands, ux, tool-routing, plugin-surface

## Prompt
The plugin registers 19 agent tools but no slash commands. Hermes plugins can register slash commands via the plugin surface. Create /opsx:* slash commands that shortcut common OpenSpec workflows, routing to the existing tool handlers. Candidate commands: /opsx:context (resolve identifier), /opsx:changes (list changes), /opsx:show (show change/spec), /opsx:idea (create idea), /opsx:promote (idea→change), /opsx:tasks (list tasks), /opsx:validate, /opsx:archive, /opsx:diff (spec diff). Each command parses user input into tool args and calls the handler, returning the result inline. This avoids the agent needing to discover and select the right tool for common operations — the user types a shortcut and the plugin routes to the correct handler. Must follow the Hermes plugin command registration API and avoid breaking prompt caching.

<!-- OPENSPEC_IDEA_ENRICHMENT_START -->
## Enrichment Report

Generated: 2026-06-23T01:55:15Z

### Problem
The plugin registers 19 agent tools but no slash commands. Users who know what they want must either type a natural language prompt and let the agent select the right tool, or manually construct tool arguments. The upstream OpenSpec CLI defines a standard set of /opsx:* commands (documented at https://github.com/Fission-AI/OpenSpec/blob/main/docs/commands.md) that provide a canonical command surface for the spec-driven workflow. Implementing these as Hermes plugin slash commands gives users a familiar, fast shortcut that routes to the plugin's existing tool handlers via ctx.dispatch_tool().

### Proposed Direction
Create a commands.py module in the plugin that implements the upstream /opsx:* command set, grouped into two tiers:

CORE PROFILE (default):
- /opsx:propose [name] — create change scaffold via openspec_change_create + return proposal authoring instructions from openspec_instructions(artifact=proposal). Fastest end-to-end path.
- /opsx:explore [topic] — create an idea via openspec_idea_create for pre-change investigation. No artifacts created.
- /opsx:apply [change] — list tasks via openspec_task_list + return apply instructions from openspec_instructions(artifact=apply). Lists incomplete tasks with progress.
- /opsx:archive [change] — validate via openspec_validate, then archive via openspec_change_archive if clean.

EXPANDED WORKFLOW COMMANDS:
- /opsx:new [name] — create bare change scaffold via openspec_change_create (no promotion).
- /opsx:continue [change] — show status via openspec_status + get instructions for next artifact based on dependency graph (proposal → design → specs → tasks).
- /opsx:ff [change] — create (if needed) + promote via openspec_change_promote in one step. Ensures tasks + spec placeholder exist.
- /opsx:verify [change] — validate via openspec_validate + status via openspec_status + task progress via openspec_task_list. Three-dimension check: completeness, correctness, coherence.
- /opsx:sync [change] — list delta specs via openspec_spec_list + show diffs via openspec_spec_diff for each. Reviews what would merge into main specs.
- /opsx:bulk-archive [change1 change2 ...] — archive multiple changes in sequence via openspec_change_archive.
- /opsx:onboard — print the workflow guide (no tool calls, static help text).

All commands accept --workdir <path> or --project <name> flags to target a repo; without flags, cwd is used.

Implementation: commands.py with a _parse_target() helper that extracts flags, per-command handlers that call ctx.dispatch_tool('openspec_*', args), and a register_commands(ctx) function. Wire in __init__.py register() by calling _commands.register_commands(ctx) after tool registration. Each handler returns a formatted string (emojis + structured output) for the chat UI.

Confirmed: ctx.register_command() accepts colon-delimited names (e.g. "opsx:propose"). The name is cleaned via .lower().strip().lstrip("/") — colons pass through. Command lookup in cli.py and gateway/run.py uses the full name including colon. No conflicts with built-in commands.

### Key Questions
- Should /opsx:propose auto-generate all artifacts (proposal, specs, design, tasks) via multiple tool calls, or just create the scaffold + return instructions so the agent/user authors them? The upstream /opsx:propose generates everything — but that's an LLM operation upstream, not a tool call. Our version should create the scaffold + return authoring instructions from openspec_instructions.
- Should /opsx:apply dispatch a subagent (via ctx.dispatch_tool('delegate_task', ...)) to implement tasks, or just list tasks + return apply instructions for the user/agent to act on? Upstream /opsx:apply does the implementation — but that requires LLM reasoning, not just tool dispatch.
- Should commands use ctx.dispatch_tool (routes through approval/redaction pipelines) or call tools.py handlers directly (bypasses agent context)? dispatch_tool is the documented pattern for slash commands that invoke tools — use that.

### Feasibility
Feasibility: High

### T-Shirt Size
T-Shirt Size: M

### Size Justification
11 command handlers, each a thin parser + 1-3 ctx.dispatch_tool calls + result formatting. The _parse_target helper and _fmt_result helper are shared. register_commands is a loop over the command table. __init__.py wiring is 5 lines. The investigation is done — API confirmed, command names confirmed, colon support confirmed.

### Risks
- Multi-step commands (/opsx:propose, /opsx:ff, /opsx:verify, /opsx:sync) dispatch multiple tool calls sequentially — if one fails mid-sequence, partial state may exist (e.g. change created but promotion failed). Handlers should report clearly which steps succeeded/failed.
- ctx.dispatch_tool routes through approval/redaction pipelines — this is correct but means commands inherit the session's approval mode. A /opsx:archive in smart approval mode might auto-approve. This is the documented behavior, not a bug, but worth noting.
- /opsx:continue's next-artifact logic depends on openspec_status output shape, which varies between CLI-backed and filesystem-backed calls. Need to handle both formats or gate on CLI availability.
- Some upstream commands (/opsx:apply, /opsx:verify) imply LLM-driven implementation or semantic analysis in the upstream CLI. Our versions return tool results + instructions rather than doing LLM work — they're routing shortcuts, not agent replacements. This is the right scope for a plugin command.

### Suggested Next Step
Promote to a change proposal. The command set, arg parsing, and tool mapping are fully specified. Implementation is mechanical.
<!-- OPENSPEC_IDEA_ENRICHMENT_END -->

## Context

The OpenSpec CLI ships 11 workflow skills as structured prompts. Each skill instructs the agent to run `openspec` CLI commands directly and parse the JSON output. The skills are tool-agnostic — they work with any AI coding assistant that has terminal access.

Our Hermes plugin wraps a subset of the CLI in 19 agent tools, but these tools return different JSON shapes. For example, `openspec_status` returns `{ok, change, status, counts}`, while the CLI returns `{changeName, schemaName, artifacts, applyRequires, planningHome, actionContext}`. The upstream skills expect the CLI's format.

This change bundles the upstream skills as-is and adds an `openspec_cli` passthrough tool, creating a clean layer separation.

## Goals / Non-Goals

**Goals:**
- Bundle all 11 upstream skills without modifying their content
- Add `openspec_cli` passthrough tool for gated CLI access
- Document the layer boundaries so future contributors understand why skills don't use plugin tools
- Auto-register skills via `ctx.register_skill()` in `register()`

**Non-Goals:**
- Contributing a Hermes adapter to upstream OpenSpec (ideal long-term, but out of scope)
- Modifying upstream skill instructions to reference Hermes-specific tools
- Generating skills at install time (requires upstream adapter)
- Slash commands (`/opsx:*`) — skills are the interface

## Decisions

### Decision 1: Bundle skills as-is, no modification

**Choice:** Reproduce the upstream `generateSkillContent()` output verbatim in `skills/<name>/SKILL.md`.

**Why not modify:** Any modification creates a diff from upstream that must be tracked. When upstream updates a prompt, we'd need to re-apply our modifications. By bundling as-is, we can regenerate from upstream with a single command and diff for changes.

**How to generate:** Run `openspec init --tools claude` into a temp directory, then copy the generated `.claude/skills/openspec-*/SKILL.md` files into our `skills/` directory. The Claude adapter's format (YAML frontmatter + body) is compatible with Hermes skills.

### Decision 2: `openspec_cli` as a separate tool, not a replacement for terminal

**Choice:** Add `openspec_cli` as a discoverable tool, but don't modify skills to use it. Skills continue to say "run `openspec new change`" and the agent uses terminal.

**Why not force skills to use it:** Modifying skill instructions = modifying upstream content = sync burden (Decision 1).

**Why add it at all:** The agent discovers tools in its tool list. When `openspec_cli` is available, the agent may prefer it over constructing a terminal command. It also provides:
- `check_fn` gating (tool only appears when CLI is installed)
- JSON output parsing
- Consistent error handling

**How the agent chooses:** Skills say "run `openspec status --change <name> --json`". The agent can do this via:
- `terminal({"command": "openspec status --change <name> --json"})`
- `openspec_cli({"command": "status --change <name>", "workdir": "..."})`

Both work. The agent picks based on availability and preference.

### Decision 3: Skill registration via directory iteration

**Choice:** In `register()`, iterate `skills/` directory, call `ctx.register_skill(child.name, child / "SKILL.md")` for each subdirectory containing `SKILL.md`.

**Why not hardcode 11 registrations:** New skills may be added upstream. Directory iteration auto-discovers them.

**Pattern:** Matches the `hermes-plugin-development` skill's documented pattern:
```python
skills_dir = _PLUGIN_DIR / "skills"
for child in sorted(skills_dir.iterdir()):
    skill_md = child / "SKILL.md"
    if child.is_dir() and skill_md.exists():
        ctx.register_skill(child.name, skill_md)
```

### Decision 4: Layer interface doc as a reference file

**Choice:** Create `docs/layers.md` as a standalone doc referenced by the plugin README.

**Why:** The layer separation is non-obvious. A future contributor looking at the plugin will see 19 tools + 11 skills + a CLI passthrough tool and wonder why they coexist. The doc explains the boundaries and prevents someone from "fixing" the duplication by rewriting skills to use tools.

## Risks / Trade-offs

- **Skill content drift from upstream** → If upstream updates a prompt, our bundled copy is stale until regenerated. Mitigated: the `generatedBy` version in skill frontmatter shows which OpenSpec version generated the content. A regeneration script (run `openspec init`, copy files) makes updates mechanical.

- **Skills reference tools the agent doesn't have** → Upstream skills mention "AskUserQuestion tool" and "TodoWrite tool" which are Claude Code/Cursor specifics. Hermes doesn't have these exact tools. Mitigated: Hermes has equivalent functionality (the agent can ask questions via `clarify`, track tasks via `todo`). The agent adapts the intent. We don't modify the skill text.

- **`openspec_cli` + terminal redundancy** → Two ways to call the same CLI. Could confuse the agent. Mitigated: `openspec_cli` is gated by `check_fn` (only appears when CLI is installed) and returns parsed JSON. Terminal is always available. The agent uses whichever is more convenient. In practice, the agent will prefer `openspec_cli` for structured queries and terminal for complex pipelines.

- **Skill schema footprint** → 11 registered skills add to the agent's context. Mitigated: skills are lazy-loaded — only the skill descriptions appear in the system prompt, not the full instructions. The agent loads a skill's full content only when it matches user intent.

## Open Questions

- Should we write a regeneration script (`scripts/regenerate-skills.sh`) that runs `openspec init` and copies the output? Or is manual regeneration sufficient given the low frequency of upstream updates?
- Should `openspec_cli` support `--schema` and `--change` as separate parameters, or keep it as a raw `command` string that the agent constructs? Raw string is simpler and matches how the CLI works.

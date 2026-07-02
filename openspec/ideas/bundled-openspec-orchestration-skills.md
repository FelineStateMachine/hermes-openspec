# Bundled openspec-orchestration skills

## Source
- Origin: human
- Created: 2026-06-23T01:37:47Z
- Tags: skills, orchestration, delegation, agent-guidance

## Prompt
The plugin ships excellent docs (docs/delegation.md, docs/lifecycle.md, docs/tool-reference.md) covering orchestration patterns, subagent delegation contracts, and parallel delegation — but the agent has no bundled skill to load this context. Create a skills/ directory in the plugin with SKILL.md files that encode the OpenSpec workflow as agent-callable procedural knowledge. Focus areas: (1) process management — the full idea→change→promote→implement→validate→archive lifecycle with when-to-use guidance and tool selection logic; (2) delegation patterns — orchestrator vs subagent contracts, the Author and Implement patterns, parallel delegation for independent task groups; (3) individual agent skills — a skill for subagents that receive a change+scope, teaching them to read specs via openspec_show, get instructions, do the work, and mark tasks done without touching lifecycle. The content already exists in docs/; this is primarily a packaging exercise into SKILL.md frontmatter + body format that the plugin register() function can wire via ctx.register_skill().

<!-- OPENSPEC_IDEA_ENRICHMENT_START -->
## Enrichment Report

Generated: 2026-06-23T01:38:42Z

### Problem
The plugin ships excellent documentation (docs/delegation.md, docs/lifecycle.md, docs/tool-reference.md) covering the full OpenSpec orchestration workflow — idea→change→promote→implement→validate→archive, subagent delegation contracts, parallel delegation patterns. But the agent has no bundled skill to auto-load this context. The agent must manually discover the docs, and subagents receiving delegated work have no procedural guidance at all — they must be told the workflow in the delegation goal/context each time. This is the single highest-value addition to the plugin that isn't a code feature.

### Proposed Direction
Create a skills/ directory in the plugin root with two or three SKILL.md files: (1) openspec-orchestration — process management skill for the orchestrator: full lifecycle states and transitions, tool selection logic (which tool for which step), when to delegate vs do directly, validation loops, promotion gates. Content derived from docs/lifecycle.md + docs/delegation.md. (2) openspec-subagent — skill for subagents receiving delegated work: read specs via openspec_show, get instructions via openspec_instructions, do the work, mark tasks done via openspec_task_set_status, never create/promote/archive. Content derived from docs/delegation.md subagent rules section. Wire both in __init__.py register() via ctx.register_skill() using the same pattern as the plugin development skill shows (iterate skills/ directory, register each SKILL.md). Add provides_skills to plugin.yaml if the manifest supports it.

### Key Questions
- Should the skills be one SKILL.md with sections, or multiple skills (orchestrator, author, implementer) registered separately? Multiple skills gives finer-grained loading but increases schema footprint.
- Should the skills reference the docs/ markdown files via file_path links (like linked_files in Hermes skills), or inline the content directly in SKILL.md?
- Does the Hermes plugin register(ctx) API support ctx.register_skill() for bundled skills, and does it handle the skills/ directory auto-discovery pattern shown in the plugin development skill?

### Feasibility
Feasibility: High

### T-Shirt Size
T-Shirt Size: M

### Size Justification
Content already exists in docs/. The work is restructuring it into SKILL.md frontmatter + body format, creating the skills/ directory, and adding ~5 lines to __init__.py register(). No new logic, no new tools, no backend changes.

### Risks
- Schema footprint — each registered skill adds to the agent's context. Two skills is manageable; more than three would be noise. Keep it to orchestrator + subagent.
- Skill content drift from docs/ — if the docs are updated but the skills aren't, they'll diverge. Mitigate by referencing the docs files as linked_files rather than inlining, so there's one source of truth.
- Need to verify that ctx.register_skill() is the correct API and that the plugin loader supports bundled skills — the build-a-plugin guide shows this pattern but it hasn't been used in this plugin yet.

### Suggested Next Step
First verify ctx.register_skill() API and plugin.yaml provides_skills field in the Hermes plugin docs. Then create the skills/ directory with openspec-orchestration and openspec-subagent SKILL.md files, wire in register().
<!-- OPENSPEC_IDEA_ENRICHMENT_END -->

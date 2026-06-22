# Orchestration Pattern

How to drive an OpenSpec change from idea to archive with Hermes agent tools,
including delegating authoring and implementation to subagents.

## Pages

| Page | For | Covers |
|---|---|---|
| [Lifecycle](lifecycle.md) | Everyone | Change states, transitions, artifact readiness |
| [Tool reference](tool-reference.md) | Two perspectives | Artifact → tool mapping (OpenSpec-native) and tool → filesystem effect (Hermes-native) |
| [Delegation](delegation.md) | Orchestrators | Full workflow, subagent patterns, parallel delegation |

### Which page to start with

- **Hermes-native** — you know the agent tools but not the OpenSpec artifact
  model. Start with [Tool reference → Tool → filesystem effect](tool-reference.md#tool--filesystem-effect).
- **OpenSpec-native** — you know the lifecycle (idea → change → specs →
  archive) but not which Hermes tool does what. Start with
  [Tool reference → Artifact → tool mapping](tool-reference.md#artifact--tool-mapping).

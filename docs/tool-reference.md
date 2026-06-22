# Tool Reference

Two perspectives on the same 15 tools. Use whichever table matches what you
already know.

## Artifact → tool mapping

If you already know OpenSpec's artifact model (proposal, design, tasks, specs,
ideas, archive), this table maps each artifact operation to the Hermes tool
that performs it.

| You want to… | OpenSpec artifact | Hermes tool | Effect |
|---|---|---|---|
| Capture a raw idea | `openspec/ideas/<slug>.md` (new) | `openspec_idea_create` | Writes the idea file |
| Add a structured evaluation to an idea | `openspec/ideas/<slug>.md` (update) | `openspec_idea_enrich` | Appends problem, direction, feasibility, T-shirt size, risks, questions, next step |
| Turn an idea into a change | `openspec/changes/<change>/` (new) | `openspec_idea_promote` | Creates the change scaffold with proposal/tasks/spec traceability |
| Create a change without an idea | `openspec/changes/<change>/` (new) | `openspec_change_create` | Creates the change scaffold directly |
| Author the proposal | `openspec/changes/<change>/proposal.md` | `openspec_instructions` → write file | Returns the authoring guide; you write the file |
| Author the design doc | `openspec/changes/<change>/design.md` | `openspec_instructions` → write file | Returns the authoring guide; you write the file |
| Author specs | `openspec/changes/<change>/specs/<spec>/spec.md` | `openspec_instructions` → write file | Returns the authoring guide; you write the file |
| Author tasks | `openspec/changes/<change>/tasks.md` | `openspec_instructions` → write file | Returns the authoring guide; you write the file |
| Mark a change ready to implement | `tasks.md` + `specs/` placeholder | `openspec_change_promote` | Ensures checklist items and spec placeholder exist |
| Read a change or spec | Any artifact | `openspec_show` | Returns JSON: proposal, tasks, design, specs, deltas |
| Get the implementation guide | `openspec apply` instructions | `openspec_instructions` (artifact=`apply`) | Returns step-by-step apply instructions |
| Track task progress | `tasks.md` checkboxes | `openspec_task_set_status` | Toggles `- [ ]` ↔ `- [x]` |
| Check what artifacts exist | Change directory | `openspec_status` | Returns which artifacts are present/missing and readiness |
| Validate before archiving | All artifacts | `openspec_validate` | Returns validation errors |
| Archive a completed change | `openspec/changes/archive/` | `openspec_change_archive` | Moves the change dir to archive |
| Reopen an archived change | `openspec/changes/` (restore) | `openspec_change_unarchive` | Moves the change dir back to active |
| Compare a change spec against its baseline | Spec files (read-only) | `openspec_spec_diff` | Returns a structured semantic delta at the requirement/scenario level plus a unified line diff fallback. Filesystem-backed. |

---

## Tool → filesystem effect

If you know the Hermes tools but want the exact filesystem mutation, this is
the reference.

### Write tools

| Tool | Filesystem effect | Lifecycle transition |
|---|---|---|
| `openspec_idea_create` | Creates `openspec/ideas/<slug>.md` | → Idea |
| `openspec_idea_enrich` | Updates `openspec/ideas/<slug>.md` with structured report | Idea (stays) |
| `openspec_idea_promote` | Creates `openspec/changes/<change>/` (proposal, tasks, specs) | Idea → Draft |
| `openspec_change_create` | Creates `openspec/changes/<change>/` (proposal, tasks, specs) | → Draft |
| `openspec_change_promote` | Ensures `tasks.md` has checklist items + `specs/` has placeholder | Draft → Todo |
| `openspec_task_set_status` | Toggles checkboxes in `openspec/changes/<change>/tasks.md` | Todo → In progress → Done |
| `openspec_change_archive` | Moves `openspec/changes/<change>/` → `openspec/changes/archive/<change>/` | Done → Archived |
| `openspec_change_unarchive` | Moves archive dir back to active changes | Archived → Done |
| `openspec_spec_diff` | Returns structured semantic delta (requirement/scenario level) between change spec and baseline, or worktree spec and HEAD. Read-only. | (no transition — read tool) |

### Read tools

| Tool | Returns | When to call |
|---|---|---|
| `openspec_context` | Repo path + change/spec content (resolves `os_*` identifiers) | First — gives you the `workdir` for all other tools |
| `openspec_list` | Changes or specs in a project | Before picking a change to work on |
| `openspec_show` | Full change or spec as JSON | To read proposal/tasks/design/specs/deltas |
| `openspec_status` | Artifact completion status (what exists, what's missing) | Before promoting or archiving |
| `openspec_instructions` | Authoring guide for an artifact (proposal, design, tasks, specs, apply) | Before authoring or implementing |
| `openspec_validate` | Validation errors for changes/specs | After editing, before archiving |
| `openspec_task_list` | Task ids, text, status, completion counts | Before marking tasks done |

> **Authoring note:** `openspec_instructions` returns the guide, not the
> artifact. After calling it, the caller writes the file (proposal.md,
> design.md, spec.md, tasks.md) using normal file tools. This is by design —
> the guide is reusable, the content is human/agent judgment.

---

← [Back to overview](index.md) · [← Previous: Lifecycle](lifecycle.md) · [Next: Delegation →](delegation.md)

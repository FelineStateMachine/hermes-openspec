# Design: Semantic Spec Diff Tool

## Context

The frontend `parseSpec` in `dashboard/dist/index.js` (lines 445–495) parses spec
markdown into `{ title, purpose, requirements: [{ name, description, scenarios: [{ name, steps }] }] }`.
This logic needs to exist in Python so the backend (`plugin_api.py`) and agent tools
(`tools.py`) can use it. The diff itself is currently `difflib.unified_diff` — line-level,
not semantic.

## Parser: `_parse_spec(md)`

Mirror the JS `parseSpec` exactly so the dashboard and tool produce identical structure.

State machine: `top → purpose → reqDesc → scenario`

| Line pattern | Action |
|---|---|
| `# Title` (not `## `) | Set title, state → `top` |
| `## Purpose` | state → `purpose` |
| `## Requirements` | state → `top` (skip header) |
| `### Requirement: Name` | Push new requirement, state → `reqDesc` |
| `#### Scenario: Name` | Push new scenario to current requirement, state → `scenario` |
| (in purpose) | Append to `purpose` |
| (in reqDesc) | Append to current requirement `description` |
| (in scenario) | Parse `**GIVEN**`/`**WHEN**`/`**THEN**` bullets into `steps` |

Return: `{ title, purpose, requirements: [{ name, description, scenarios: [{ name, steps: [{ type, text }] }] }] }`

## Diff: `_semantic_spec_diff(before_md, after_md)`

1. Parse both specs.
2. Build dicts keyed by requirement name for O(1) lookup.
3. Classify each requirement:
   - In after only → `added`
   - In before only → `removed`
   - In both, same description + same scenarios → `unchanged`
   - In both, different → `modified`
4. For modified requirements, diff scenarios the same way (by scenario name).
5. Return:

```python
{
    "status": "added" | "modified" | "deleted" | "unchanged",
    "requirements": {
        "added": [{ name, description, scenarios }],
        "modified": [{
            "name",
            "before": { description, scenarios },
            "after": { description, scenarios },
            "scenarios_added": [...],
            "scenarios_modified": [...],
            "scenarios_removed": [...],
        }],
        "removed": [{ name, description, scenarios }],
        "unchanged": ["req name", ...],
    },
}
```

Overall status: `added` if before is None/empty, `deleted` if after is None/empty,
`unchanged` if all requirements unchanged, else `modified`.

## Tool: `openspec_spec_diff`

### Parameters

| Param | Required | Description |
|---|---|---|
| `workdir` | yes (or `identifier`) | Project directory |
| `spec` | yes | Spec name (e.g. `agent-tools`) |
| `change` | no | Change id — when provided, diff change spec vs baseline |

### Resolution

- `change` provided:
  - Change spec: `openspec/changes/<change>/specs/<spec>/spec.md`
  - Baseline: `openspec/specs/<spec>/spec.md`
  - If change spec missing → `ok: false, error: "change spec not found"`
  - If baseline missing → status `added`, all requirements in `added`
- `change` omitted:
  - Worktree spec: `openspec/specs/<spec>/spec.md` (current content)
  - Baseline: `git show HEAD:openspec/specs/<spec>/spec.md`
  - If git unavailable → `ok: false, error: "git required for HEAD comparison"`

### Output

```json
{
    "ok": true,
    "spec": "agent-tools",
    "change": "add-idea-tools",
    "status": "modified",
    "baseline_exists": true,
    "requirements": { "added": [...], "modified": [...], "removed": [...], "unchanged": [...] },
    "line_diff": "--- before/...\n+++ after/...\n@@ ..."
}
```

## Registration

Filesystem-backed — always available, no `check_fn` gating. Same pattern as
`openspec_context`, `openspec_idea_create`, etc.

## Sharing with the dashboard

The `_parse_spec` and `_semantic_spec_diff` functions live in `tools.py`. The
dashboard backend (`plugin_api.py`) imports them the same way it imports
`registry.py` — via `importlib.util.spec_from_file_location`. This avoids
circular imports and keeps the plugin self-contained.

Alternatively, extract into a `spec_parser.py` module that both `tools.py` and
`plugin_api.py` import directly. Preferred — cleaner separation, testable in
isolation.

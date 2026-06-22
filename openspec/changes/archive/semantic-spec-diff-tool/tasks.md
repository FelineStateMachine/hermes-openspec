## 1. Tasks

- [x] 1.1 Add _parse_spec(md) Python function to tools.py mirroring the frontend parseSpec parser (title, purpose, requirements with name/description/scenarios, scenarios with name/steps)
- [x] 1.2 Add _semantic_spec_diff(before_md, after_md) function returning structured delta: requirements.added/modified/removed/unchanged, with scenario-level diffs inside modified requirements
- [x] 1.3 Add openspec_spec_diff tool handler: takes workdir, spec, optional change; diffs change spec against baseline spec when change is provided, diffs worktree spec against HEAD when change is omitted
- [x] 1.4 Add OPENSPEC_SPEC_DIFF schema to schemas.py
- [x] 1.5 Register openspec_spec_diff in __init__.py (filesystem-backed, always available — no check_fn gating)
- [x] 1.6 Add openspec_spec_diff to provides_tools in plugin.yaml
- [x] 1.7 Write tests for parser, semantic diff (added/modified/removed/unchanged requirements, scenario-level deltas), and tool handler (change vs baseline, worktree vs HEAD, missing spec handling)

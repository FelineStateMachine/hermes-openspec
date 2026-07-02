## Tasks

- [x] Create `skills/` directory in plugin root
- [x] Generate all 11 upstream skill files via `openspec init --tools claude` into a temp dir
- [x] Copy generated `SKILL.md` files into `skills/<name>/` (11 directories)
- [x] Add `openspec_cli` tool: schema in `schemas.py`, handler in `tools.py`
- [x] Gate `openspec_cli` with `check_fn` (same `_openspec_bin() is not None` check)
- [x] Add skill registration loop in `__init__.py` `register()` — iterate `skills/`, call `ctx.register_skill()`
- [x] Register `openspec_cli` in `__init__.py` `register()`
- [x] Add `openspec_cli` to `plugin.yaml` `provides_tools`
- [x] Write `docs/layers.md` documenting the layer boundaries
- [x] Update `README.md` to mention bundled skills and layer architecture
- [x] Test: skills are discoverable via `hermes skills list` when plugin is installed
- [x] Test: `/skill openspec-propose` loads the skill into a session
- [x] Test: `openspec_cli` tool appears only when openspec binary is available
- [x] Test: `openspec_cli` returns raw JSON from `openspec status --change <name> --json`
- [x] Test: skills + plugin tools coexist without conflicts

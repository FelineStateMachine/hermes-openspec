## Tasks

- [ ] Create `commands.py` with `_parse_target()`, `_dispatch()`, `_fmt_result()` helpers
- [ ] Implement core commands: `/opsx:propose`, `/opsx:explore`, `/opsx:apply`, `/opsx:archive`
- [ ] Implement expanded commands: `/opsx:new`, `/opsx:continue`, `/opsx:ff`, `/opsx:verify`, `/opsx:sync`, `/opsx:bulk-archive`
- [ ] Implement `/opsx:onboard` static help text
- [ ] Implement `_next_artifact()` helper for `/opsx:continue` artifact dependency logic
- [ ] Add `register_commands(ctx)` function with command table
- [ ] Wire `_commands.register_commands(ctx)` in `__init__.py` `register()`
- [ ] Test: each command dispatches the correct tool(s) with parsed args
- [ ] Test: `--workdir` and `--project` flags are parsed correctly
- [ ] Test: commands appear in `/help` output and autocomplete
- [ ] Test: commands work in gateway (Discord/Telegram) not just CLI

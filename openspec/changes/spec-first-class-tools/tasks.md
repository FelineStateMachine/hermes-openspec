## 1. Tasks

- [ ] 1.1 1.1 Add `openspec_spec_create` schema to schemas.py (structured input: title, purpose, requirements array with name/description/scenarios)
- [ ] 1.2 1.2 Add `openspec_spec_show` schema (inputs: spec name, optional change id, optional workdir)
- [ ] 1.3 1.3 Add `openspec_spec_list` schema (inputs: optional change id, optional workdir)
- [ ] 1.4 1.4 Register all three tools in __init__.py and plugin.yaml
- [ ] 1.5 2.1 Add `spec_to_markdown` serializer to spec_parser.py (inverse of parse_spec — structured input → formatted spec.md)
- [ ] 1.6 2.2 Implement `openspec_spec_create` handler in tools.py (slug validation, change-scoped vs baseline, overwrite protection)
- [ ] 1.7 2.3 Implement `openspec_spec_show` handler in tools.py (uses parse_spec, returns structured JSON)
- [ ] 1.8 2.4 Implement `openspec_spec_list` handler in tools.py (directory walk: change specs or baseline specs)
- [ ] 1.9 3.1 Add tests for spec_create (structured input → valid markdown, overwrite refusal, invalid slug)
- [ ] 1.10 3.2 Add tests for spec_show (parse round-trip, missing spec, change vs baseline)
- [ ] 1.11 3.3 Add tests for spec_list (change-scoped, baseline, empty)
- [ ] 1.12 4.1 Update agent-tools spec with new requirements for create/show/list
- [ ] 1.13 4.2 Update README and docs/tool-reference.md tool counts and tables
- [ ] 1.14 4.3 Run full test suite and openspec validate --strict

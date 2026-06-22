## 1. Specs

- [x] 1.1 Create an OpenSpec change for initialization/instructions fixes
- [x] 1.2 Add requirement deltas for dashboard source initialization
- [x] 1.3 Add requirement deltas for agent instruction fallback

## 2. Tests

- [x] 2.1 Add regression test for `artifact=spec` instructions in a fresh initialized repo
- [x] 2.2 Add regression test for canonical dashboard initialization directories
- [x] 2.3 Add regression test for fallback initialization layout without OpenSpec CLI

## 3. Implementation

- [x] 3.1 Normalize source initialization layout after CLI and fallback init
- [x] 3.2 Add `openspec_instructions` fresh-repo template fallback
- [x] 3.3 Normalize `spec` artifact alias to `specs`
- [x] 3.4 Keep repo-root pytest collection/import working

## 4. Validation

- [x] 4.1 Run targeted pytest regression tests
- [x] 4.2 Run OpenSpec strict validation
- [x] 4.3 Check git status and report remaining issues

# Contributing to hermes-openspec

Thanks for your interest in improving this plugin. This is a small, focused
project — the bar is a clean diff that fixes a real bug or adds a feature
that fits the plugin's scope (OpenSpec integration for Hermes Agent).

## Reporting issues

1. **Check existing issues** first to avoid duplicates.
2. **Include a reproduction**: the exact steps, what you expected, and what
   happened. If it's a dashboard issue, note your browser and Hermes version.
3. **Include the error**: paste the full traceback or the HTTP response. A
   screenshot of the dashboard is fine for UI bugs.
4. **Note your environment**: OS, Hermes version, OpenSpec CLI version
   (`openspec --version`), and whether the `openspec` binary is on `PATH`.

## Submitting pull requests

### Before you start

If the change is non-trivial (new endpoint, new UI component, schema change),
open an issue or draft PR first to scope it. This avoids wasted work on
something that doesn't fit the design.

### Branches

This repo uses trunk-based development on `main`:

- `main` is the only long-lived branch. All PRs target `main`.
- Branch short-lived feature branches off `main`, PR back, delete after merge.
- Releases are tagged on `main` (`v0.1.0`, `v1.0.0`, …). No release branch.

### What we look for

- **Fix real bugs.** Reproduce the symptom on `main`, point to the exact line,
  and fix the whole bug class — not just the one site you hit.
- **Keep the core narrow.** This plugin extends Hermes at the edge. Don't add
  hooks, callbacks, or extension points with no concrete consumer.
- **No new env vars for non-secret config.** Behavioral settings go in the
  Hermes config, not `.env`. Only credentials belong in `.env`.
- **Match existing style.** The frontend is a hand-written IIFE in
  `dashboard/dist/index.js` — no build step, no framework, no JSX. The backend
  is plain FastAPI in `dashboard/plugin_api.py`. Follow the patterns already
  there.
- **Don't break the registry DB.** `registry.py` manages a SQLite DB at
  `~/.hermes/openspec.db`. Schema changes must be backward-compatible or
  include a migration. Never delete user data.

### Testing

There's no automated test suite yet. Before submitting:

1. Install your changes: copy the plugin dir to `~/.hermes/plugins/openspec/`
   (only `openspec.db` persists across updates — everything else is
   overwritten).
2. Restart Hermes and verify the dashboard tab loads.
3. Exercise the affected code path manually — register a source, browse
   changes/specs, trigger the bug you fixed.
4. If you added a backend route, confirm it returns sane responses for both
   the happy path and error cases (missing source, invalid path, etc.).

### Commit messages

Follow the existing convention:

```
type: short description

Optional body explaining why, not what.
```

Types: `fix`, `feat`, `docs`, `refactor`, `chore`.

### Deploying for development

```bash
# Copy from repo to installed plugin location
cp -r ~/repos/hermes-openspec/* ~/.hermes/plugins/openspec/

# If backend routes changed, restart Hermes to remount them
# Frontend-only changes can be hot-reloaded via dashboard rescan
```

The `openspec.db` database lives at `~/.hermes/openspec.db` (outside the
plugin directory) and survives plugin updates. Do not include it in PRs.

## Questions

Open an issue with the `question` label.

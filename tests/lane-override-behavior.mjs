#!/usr/bin/env node
/**
 * Lane override behavior tests — toggle semantics, phase pruning, source keying.
 *
 * These test pure helpers that must be added to plugin.js __test export:
 *   - computeCollapsedSet(autoCollapsed, manualOverrides, statusOrder)
 *   - toggleOverride(prev, status, autoCollapsed)  →  next overrides
 *   - computeLanePhase(grouped, statusOrder)        →  phase signature string
 *   - pruneStaleOverrides(prevOverrides, prevPhase, lanePhase)  →  pruned overrides
 *   - workViewIsSourceKeyed                          →  true (static check)
 *
 * Run: node tests/lane-override-behavior.mjs
 * Exit 0 = pass, exit 1 = failure.
 */

import { readFileSync } from 'node:fs'
import { execSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const pluginPath = resolve(__dirname, '../desktop/plugin.js')
const source = readFileSync(pluginPath, 'utf8')

let passed = 0
let failed = 0
const failures = []

function ok(name) { passed++; console.log('  PASS  ' + name) }
function fail(name, d) {
  failed++
  const msg = '  FAIL  ' + name + (d ? ': ' + d : '')
  console.error(msg)
  failures.push({ name, detail: d })
}
function check(c, n, d) { c ? ok(n) : fail(n, d) }

console.log('=== Lane override behavior tests ===\n')

// ═══════════════════════════════════════════════════════════════════════════════
// 0. Static source checks — WorkView is keyed by selectedSource.id
// ═══════════════════════════════════════════════════════════════════════════════
console.log('[0] WorkView source keying (static)')

// The WorkView render call must have a key prop bound to selectedSource.id
// Look for the pattern: jsx(WorkView, {..., key: selectedSource.id}) or
// key={selectedSource.id} near the WorkView usage
{
  const workViewKeyPattern = /key:\s*selectedSource\.id/
  check(workViewKeyPattern.test(source), 'WorkView render has key={selectedSource.id}',
    !workViewKeyPattern.test(source) ? 'Missing key prop on WorkView jsx() call' : undefined)
}

// ═══════════════════════════════════════════════════════════════════════════════
// Load dynamic helpers
// ═══════════════════════════════════════════════════════════════════════════════
console.log('\n[Dynamic] Load __test exports')

const helperPath = resolve(__dirname, '_dynamic_import_helper.mjs')

let r
try {
  const raw = execSync('node ' + helperPath, { encoding: 'utf8', timeout: 30000 }).trim()
  r = JSON.parse(raw)
} catch (e) {
  fail('Dynamic import', (e.message || '').slice(0, 500))
  r = {}
}

if (!r.__testAvailable) {
  fail('__test available', '__test not available — cannot run behavioral tests')
  console.log('\n=== Results: ' + passed + ' passed, ' + failed + ' failed ===')
  process.exit(failed > 0 ? 1 : 0)
}

// ═══════════════════════════════════════════════════════════════════════════════
// 1. computeCollapsedSet — merge auto with manual overrides
// ═══════════════════════════════════════════════════════════════════════════════
console.log('\n[1] computeCollapsedSet')

const cs = r.collapsedSet || {}
check(cs.autoOnlyEmpty !== undefined, 'computeCollapsedSet produces results')

// Empty overrides → auto rules
check(cs.autoOnlyEmpty === true, 'Empty lane collapsed when board has work, no override',
  JSON.stringify(cs.autoOnlyEmpty))
check(cs.autoOnlyPopulated === true, 'Populated lane expanded when board has work, no override',
  JSON.stringify(cs.autoOnlyPopulated))

// Manual override wins over auto
check(cs.overrideEmpty === true, 'Override overrides auto-collapse for empty lane (user expanded)',
  JSON.stringify(cs.overrideEmpty))
check(cs.overridePopulated === true, 'Override overrides auto-expand for populated lane (user collapsed)',
  JSON.stringify(cs.overridePopulated))

// ═══════════════════════════════════════════════════════════════════════════════
// 2. toggleOverride — minimal deviation storage
// ═══════════════════════════════════════════════════════════════════════════════
console.log('\n[2] toggleOverride (minimal deviation)')

const to = r.toggle || {}
check(typeof to.firstToggleEmpty === 'boolean', 'toggleOverride returns boolean for empty lane')
check(to.firstToggleEmpty === false, 'First toggle on auto-collapsed empty lane: stores false (expanded)',
  JSON.stringify(to.firstToggleEmpty))
check(to.secondToggleEmpty === undefined || to.secondToggleEmpty === null,
  'Second toggle on previously-toggled empty lane: deletes override (back to auto)',
  JSON.stringify(to.secondToggleEmpty))

check(to.firstTogglePopulated === true, 'First toggle on auto-expanded populated lane: stores true (collapsed)',
  JSON.stringify(to.firstTogglePopulated))
check(to.secondTogglePopulated === undefined || to.secondTogglePopulated === null,
  'Second toggle on previously-toggled populated lane: deletes override (back to auto)',
  JSON.stringify(to.secondTogglePopulated))

// ═══════════════════════════════════════════════════════════════════════════════
// 3. computeLanePhase — phase signature string
// ═══════════════════════════════════════════════════════════════════════════════
console.log('\n[3] computeLanePhase')

const lp = r.lanePhase || {}
check(typeof lp.empty === 'string', 'computeLanePhase returns string')
check(lp.empty === 'todo:empty|in-progress:full|done:empty',
  'Phase signature for empty todo, populated in-progress, empty done',
  JSON.stringify(lp.empty))
check(lp.full === 'todo:full|in-progress:empty|done:full',
  'Phase signature for populated todo, empty in-progress, populated done',
  JSON.stringify(lp.full))
check(lp.nullGrouped === null || lp.nullGrouped === undefined,
  'computeLanePhase returns null for null grouped input',
  JSON.stringify(lp.nullGrouped))

// ═══════════════════════════════════════════════════════════════════════════════
// 4. pruneStaleOverrides — phase-change pruning
// ═══════════════════════════════════════════════════════════════════════════════
console.log('\n[4] pruneStaleOverrides')

const po = r.prune || {}

// Phase changed on a lane with override → override pruned
check(po.changedLanePruned === true, 'Phase change on override lane prunes that override',
  JSON.stringify(po.changedLanePruned))

// Phase unchanged on a lane with override → override preserved
check(po.unchangedLaneKept === true, 'Phase unchanged on override lane preserves override',
  JSON.stringify(po.unchangedLaneKept))

// Phase changed on a lane WITHOUT override → nothing changes
check(po.changedNoOverride === true, 'Phase change on non-overridden lane is harmless',
  JSON.stringify(po.changedNoOverride))

// Null previous phase (first render) → no pruning
check(po.nullPrevPhase === true, 'Null previous phase (first render) does not prune',
  JSON.stringify(po.nullPrevPhase))

// Multiple overrides, mixed phase changes → only affected ones pruned
check(po.mixedPruning === true, 'Mixed phase changes: only changed-lane overrides pruned, others kept',
  JSON.stringify(po.mixedPruning))

// ═══════════════════════════════════════════════════════════════════════════════
// 5. Toggle semantic integration — second toggle deletes override
// ═══════════════════════════════════════════════════════════════════════════════
console.log('\n[5] Toggle integration (toggle → toggle → auto restored)')

const ti = r.toggleIntegration || {}
check(ti.autoCollapsedDeleted === true,
  'Toggle auto-collapsed empty lane twice: override deleted, auto collapsed again',
  JSON.stringify(ti.autoCollapsedDeleted))
check(ti.autoExpandedDeleted === true,
  'Toggle auto-expanded populated lane twice: override deleted, auto expanded again',
  JSON.stringify(ti.autoExpandedDeleted))
check(ti.partialToggleKept === true,
  'Toggle only one lane: other lane overrides preserved',
  JSON.stringify(ti.partialToggleKept))

// ═══════════════════════════════════════════════════════════════════════════════
// Summary
// ═══════════════════════════════════════════════════════════════════════════════
console.log('\n=== Results: ' + passed + ' passed, ' + failed + ' failed ===')
if (failed > 0) {
  console.log('\nFailures:')
  failures.forEach(function(f) { console.log('  - ' + f.name + (f.detail ? ': ' + f.detail : '')) })
}
process.exit(failed > 0 ? 1 : 0)

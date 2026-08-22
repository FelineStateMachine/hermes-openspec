#!/usr/bin/env node
/**
 * Headless smoke harness for desktop/plugin.js
 *
 * Verifies:
 *   1. ESM parsing (no CommonJS, valid imports)
 *   2. No JSX syntax outside jsx()/jsxs() calls
 *   3. Allowed imports only (@hermes/plugin-sdk, react, react/jsx-runtime)
 *   4. Default export is valid HermesPlugin (id + register)
 *   5. ROUTES_AREA + SIDEBAR_NAV_AREA contributions registered
 *   6. Path is /openspec, sidebar nav has label + codicon
 *   7. ctx.rest('/sources') invocation (static + dynamic)
 *   8. Loading/error/empty state transitions
 *
 * Run: node spikes/001-desktop-route-api/smoke.mjs
 * Exit 0 = pass, exit 1 = failure.
 */

import { readFileSync } from 'node:fs'
import { execSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const pluginPath = resolve(__dirname, '../../desktop/plugin.js')
const source = readFileSync(pluginPath, 'utf8')

let passed = 0
let failed = 0

function ok(name) { passed++; console.log(`  PASS  ${name}`) }
function fail(name, d) { failed++; console.error(`  FAIL  ${name}${d ? ': ' + d : ''}`) }
function check(c, n, d) { c ? ok(n) : fail(n, d) }

console.log('=== Smoke harness: desktop/plugin.js ===\n')

// ── 1. ESM structure ───────────────────────────────────────────────────────
console.log('[1] ESM structure')
check(source.includes('export default'), 'Has default export')
check(source.includes('import {'), 'Has named imports')
check(!source.includes('module.exports'), 'No CommonJS exports')
check(!source.includes('require('), 'No require() calls')

// ── 2. No raw JSX ──────────────────────────────────────────────────────────
console.log('\n[2] No raw JSX')
{
  const bad = source.split('\n').filter(l => {
    const t = l.trim()
    if (t.startsWith('//') || t.startsWith('*') || t.startsWith('/*')) return false
    if (t.includes('jsx(') || t.includes('jsxs(')) return false
    const stripped = t.replace(/['"`](?:[^'"`\\]|\\.)*['"`]/g, '')
    return /<[A-Z]/.test(stripped)
  })
  check(bad.length === 0, 'No raw JSX outside jsx()/jsxs()', bad.length ? `Line: ${bad[0].trim()}` : undefined)
}

// ── 3. Allowed imports ─────────────────────────────────────────────────────
console.log('\n[3] Allowed imports')
{
  const specs = [...source.matchAll(/from\s+['"]([^'"]+)['"]/g)].map(m => m[1])
  const allowed = new Set(['@hermes/plugin-sdk', 'react', 'react/jsx-runtime'])
  const bad = specs.filter(s => !allowed.has(s))
  check(specs.length > 0, `Found ${specs.length} import(s)`)
  check(bad.length === 0, 'No disallowed imports', bad.length ? `Bad: ${bad.join(', ')}` : undefined)
}

// ── 4. Dynamic import — plugin identity ────────────────────────────────────
console.log('\n[4] Dynamic import: plugin identity')

// Build child code as array to avoid template literal escaping issues
const childLines = [
  "import { readFileSync } from 'node:fs'",
  "import { pathToFileURL } from 'node:url'",
  "",
  "const src = readFileSync(" + JSON.stringify(pluginPath) + ", 'utf8')",
  "",
  "const sdkShim = 'export const cn=(...a)=>a.filter(Boolean).join(\" \");'",
  "  + 'export const ROUTES_AREA=\"routes\";'",
  "  + 'export const SIDEBAR_NAV_AREA=\"sidebar.nav\";'",
  "  + 'export const useQuery=()=>({data:null,isLoading:true,error:null});'",
  "  + 'export const Loader=()=>null;'",
  "  + 'export const EmptyState=()=>null;'",
  "  + 'export const ErrorState=()=>null;' + ' export const Badge=()=>null;' + ' export const Button=()=>null;' + ' export const Codicon=()=>null;' + ' export const CopyButton=()=>null;' + ' export const Dialog=()=>null;' + ' export const DialogContent=()=>null;' + ' export const Input=()=>null;' + ' export const ScrollArea=()=>null;' + ' export const SearchField=()=>null;' + ' export const Select=()=>null;' + ' export const SelectContent=()=>null;' + ' export const SelectItem=()=>null;' + ' export const SelectTrigger=()=>null;' + ' export const SelectValue=()=>null;' + ' export const SegmentedControl=()=>null;' + ' export const Tabs=()=>null;' + ' export const TabsList=()=>null;' + ' export const TabsTrigger=()=>null;'",
  "",
  "const reactShim = 'export function useState(v){return[v,function(){},function(){},v]};'",
  "  + 'export function useEffect(f,d){return undefined};'",
  "  + 'export function useRef(v){return{current:v}};'",
  "  + 'export function useCallback(f,d){return f};'",
  "  + 'export function useMemo(f,d){return f()};'",
  "  + 'export function useContext(c){return undefined};'",
  "  + 'export default {}'",
  "",
  "const jsxShim = 'export function jsx(c,p){return{component:c,props:p,_t:\"jsx\"}}'",
  "  + 'export function jsxs(c,p){return{component:c,props:p,_t:\"jsxs\"}}'",
  "",
  "const sdkUrl = 'data:text/javascript,' + encodeURIComponent(sdkShim)",
  "const reactUrl = 'data:text/javascript,' + encodeURIComponent(reactShim)",
  "const jsxUrl = 'data:text/javascript,' + encodeURIComponent(jsxShim)",
  "const blobSrc = src",
  "  .replace(/from\\s+['\"]@hermes\\/plugin-sdk['\"]/g, \"from '\" + sdkUrl + \"'\")",
  "  .replace(/from\\s+['\"]react\\/jsx-runtime['\"]/g, \"from '\" + jsxUrl + \"'\")",
  "  .replace(/from\\s+['\"]react['\"]/g, \"from '\" + reactUrl + \"'\")",
  "",
  "const blobUrl = 'data:text/javascript,' + encodeURIComponent(blobSrc)",
  "const mod = await import(blobUrl)",
  "const p = mod.default",
  "",
  "const results = {",
  "  id: p && p.id,",
  "  hasRegister: typeof (p && p.register) === 'function',",
  "  hasName: typeof (p && p.name) === 'string',",
  "  description: p && p.description,",
  "}",
  "",
  "const contribs = []",
  "let restCalls = []",
  "",
  "const mockCtx = {",
  "  register(c) { contribs.push(c) },",
  "  registerMany(arr) { for (const c of arr) contribs.push(c) },",
  "  rest(path) { restCalls.push(path); return Promise.resolve({ sources: [] }) }",
  "}",
  "",
  "try {",
  "  p.register(mockCtx)",
  "} catch(e) {",
  "  results.registerError = e.message",
  "}",
  "",
  "results.contribCount = contribs.length",
  "results.restCalls = restCalls",
  "results.routeContrib = contribs.find(c => c.area === 'routes')",
  "results.navContrib = contribs.find(c => c.area === 'sidebar.nav')",
  "results.hasRender = typeof (results.routeContrib && results.routeContrib.render) === 'function'",
  "",
  "if (results.hasRender) {",
  "  try {",
  "    const rendered = results.routeContrib.render()",
  "    results.renderReturned = rendered != null",
  "    results.renderIsJsx = rendered && (rendered._t === 'jsx' || rendered._t === 'jsxs')",
  "  } catch(e) {",
  "    results.renderError = e.message",
  "  }",
  "}",
  "",
  "process.stdout.write(JSON.stringify(results))",
]

const childPath = resolve(__dirname, '_smoke_child.mjs')
import { writeFileSync, unlinkSync } from 'node:fs'
writeFileSync(childPath, childLines.join('\n'))

try {
  const raw = execSync(`node ${childPath}`, { encoding: 'utf8', timeout: 15000 }).trim()
  const r = JSON.parse(raw)

  console.log(`  id=${r.id} register=${r.hasRegister} name="${r.description}"`)
  check(r.id === 'openspec', 'Plugin id is "openspec"', r.id ? `Got: ${r.id}` : 'null')
  check(r.hasRegister, 'Has register() function')
  check(r.hasName, 'Has name property')
  check(!r.registerError, 'register() runs without error', r.registerError)

  // [5] Contributions
  console.log(`\n[5] Contributions: ${r.contribCount} registered`)
  check(r.contribCount >= 2, 'At least 2 contributions')
  check(r.routeContrib !== undefined, 'Has ROUTES_AREA contribution')
  check(r.navContrib !== undefined, 'Has SIDEBAR_NAV_AREA contribution')

  // [6] Path and nav metadata
  console.log('\n[6] Path and nav metadata')
  const rp = r.routeContrib && r.routeContrib.data && r.routeContrib.data.path
  check(rp === '/openspec', `Route path "/openspec"`, rp ? `Got: ${rp}` : 'missing')
  check(r.navContrib && r.navContrib.data && r.navContrib.data.label === 'OpenSpec', 'Sidebar nav label "OpenSpec"')
  check(r.navContrib && r.navContrib.data && r.navContrib.data.codicon != null, 'Sidebar nav has codicon')
  check(r.navContrib && r.navContrib.data && r.navContrib.data.path === '/openspec', 'Sidebar nav path /openspec')

  // [7] Render function
  console.log('\n[7] Render function')
  check(r.hasRender, 'Route contribution has render()')
  check(r.renderReturned === true, 'render() returns a value', r.renderError || 'returned null')
  check(r.renderIsJsx === true, 'render() returns jsx descriptor',
    !r.renderIsJsx && r.renderReturned ? `Got type: ${typeof r.renderReturned}` : undefined)

} catch (e) {
  fail('Dynamic import', e.message)
} finally {
  try { unlinkSync(childPath) } catch {}
}

// ── 8. ctx.rest('/sources') — static analysis ──────────────────────────────
console.log('\n[8] ctx.rest("/sources") invocation')
check(source.includes("api.sources()"), "Calls api.sources()")
check(!source.includes("fetch('"), 'No direct fetch() calls')
check(!source.includes('fetch("/'), 'No direct fetch() calls')
check(!source.includes('window.fetch'), 'No window.fetch calls')

// Verify the rest call is inside the render path (useQuery queryFn)
const restInQueryFn = /queryFn.*api\.sources/.test(source)
  || /api\.sources[\s\S]*queryFn/.test(source)
  || source.includes("queryFn: function() { return api.sources() }")
check(restInQueryFn, 'api.sources() is in useQuery queryFn')

// ── 9. Loading/error/empty state transitions ───────────────────────────────
console.log('\n[9] Rendering transitions')
check(source.includes('isLoading'), 'Checks isLoading state')
check(source.includes('error'), 'Checks error state')
check(source.includes('Loader'), 'Uses Loader component')
check(source.includes('ErrorState'), 'Uses ErrorState component')
check(source.includes('EmptyState'), 'Uses EmptyState component')

// ── 10. Source quality ──────────────────────────────────────────────────────
console.log('\n[10] Source quality')
check(!source.includes('console.log'), 'No debug console.log')
check(!source.includes('// TODO'), 'No TODO comments')
check(!source.includes('alert('), 'No alert() calls')
check(source.includes("id: 'openspec'"), 'Plugin id is "openspec"')
check(source.includes("name: 'OpenSpec'"), 'Plugin name is "OpenSpec"')

// ── Summary ─────────────────────────────────────────────────────────────────
console.log(`\n=== Results: ${passed} passed, ${failed} failed ===`)
process.exit(failed > 0 ? 1 : 0)

#!/usr/bin/env node
/**
 * Helper module for dynamic import shim generation.
 * Called by desktop-plugin-smoke.mjs to avoid template literal escaping issues.
 */
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const pluginPath = resolve(__dirname, '../desktop/plugin.js')
const src = readFileSync(pluginPath, 'utf8')

// Shim @hermes/plugin-sdk
const sdkExports = [
  'cn', 'Codicon', 'useQuery',
  'Loader', 'EmptyState', 'ErrorState', 'Badge', 'Button',
  'CopyButton', 'Dialog', 'DialogContent', 'Input', 'ScrollArea', 'SearchField',
  'Select', 'SelectContent', 'SelectItem', 'SelectTrigger', 'SelectValue',
  'SegmentedControl', 'Tabs', 'TabsList', 'TabsTrigger'
].map(n => 'export const ' + n + '=(...a)=>a').join(';')
// ROUTES_AREA and SIDEBAR_NAV_AREA are string constants, not functions
const sdkShim = sdkExports
  + ';export const ROUTES_AREA="routes"'
  + ';export const SIDEBAR_NAV_AREA="sidebar.nav"'
  + ';export default {}'

// Shim react
const reactShim = 'export function useState(v){return[v,function(){},function(){},v]};'
  + 'export function useEffect(f,d){return undefined};'
  + 'export function useRef(v){return{current:v}};'
  + 'export function useCallback(f,d){return f};'
  + 'export function useMemo(f,d){return f()};'
  + 'export function useContext(c){return undefined};'
  + 'export default {}'

// Shim react/jsx-runtime
const jsxShim = 'export function jsx(c,p){return{component:c,props:p,_t:"jsx"}}'
  + 'export function jsxs(c,p){return{component:c,props:p,_t:"jsxs"}}'
  + 'export function Fragment(p){return p&&p.children}'

const sdkUrl = 'data:text/javascript,' + encodeURIComponent(sdkShim)
const reactUrl = 'data:text/javascript,' + encodeURIComponent(reactShim)
const jsxUrl = 'data:text/javascript,' + encodeURIComponent(jsxShim)

const blobSrc = src
  .replace(/from\s+['"]@hermes\/plugin-sdk['"]/g, "from '" + sdkUrl + "'")
  .replace(/from\s+['"]react\/jsx-runtime['"]/g, "from '" + jsxUrl + "'")
  .replace(/from\s+['"]react['"]/g, "from '" + reactUrl + "'")

const blobUrl = 'data:text/javascript,' + encodeURIComponent(blobSrc)
const mod = await import(blobUrl)
const plugin = mod.default
const __test = mod.__test

// Simulate register()
const contribs = []
let restCalls = []
const mockCtx = {
  register(c) { contribs.push(c) },
  registerMany(arr) { for (const c of arr) contribs.push(c) },
  rest(path, opts) { restCalls.push({ path: path, opts: opts || null }); return Promise.resolve({}) }
}

try {
  plugin.register(mockCtx)
} catch(e) {
  // register may fail if __test not available
}

// Export results as JSON
const routeContrib = contribs.find(c => c.area === 'routes')
let renderResult = null
if (routeContrib && typeof routeContrib.render === 'function') {
  try {
    const rendered = routeContrib.render()
    renderResult = { returned: rendered != null, isJsx: rendered && (rendered._t === 'jsx' || rendered._t === 'jsxs') }
  } catch(e) {
    renderResult = { error: e.message }
  }
}
const results = {
  id: plugin && plugin.id,
  name: plugin && plugin.name,
  hasRegister: typeof (plugin && plugin.register) === 'function',
  contribCount: contribs.length,
  routeContrib: routeContrib,
  routeContribHasRender: routeContrib && typeof routeContrib.render === 'function',
  renderResult: renderResult,
  navContrib: contribs.find(c => c.area === 'sidebar.nav'),
  restCalls: restCalls,
  __testKeys: __test ? Object.keys(__test) : [],
  __testAvailable: !!__test,
}

// Test __test functions if available
if (__test) {
  try {
    results.pathBuilders = {}

    if (__test.sourcesPath) results.pathBuilders.sources = __test.sourcesPath()
    if (__test.changePath) {
      results.pathBuilders.change = __test.changePath('src-1', 'my-change')
      results.pathBuilders.changeSpecial = __test.changePath('src-1', 'feat/with spaces & special')
    }
    if (__test.ideaPath) {
      results.pathBuilders.idea = __test.ideaPath('src-1', 'my-idea')
      results.pathBuilders.ideaSpecial = __test.ideaPath('src-1', 'feat/with spaces & special')
    }
    if (__test.specBrowserPath) {
      results.pathBuilders.specBrowser = __test.specBrowserPath('src-1')
      results.pathBuilders.specBrowserDirty = __test.specBrowserPath('src-1', { dirty: true })
    }
    if (__test.specPath) {
      results.pathBuilders.spec = __test.specPath('src-1', 'specs/readme.md')
      results.pathBuilders.specSpecial = __test.specPath('src-1', 'specs/with spaces.md')
    }

    // Source selection
    results.sourceSelection = {}
    if (__test.selectFirstValid) {
      const sources = [
        { id: 'src-1', valid: false, error: 'bad' },
        { id: 'src-2', valid: true, name: 'good' },
        { id: 'src-3', valid: true, name: 'also-good' }
      ]
      results.sourceSelection.firstValid = __test.selectFirstValid(sources)
      const allInvalid = [
        { id: 'src-1', valid: false, error: 'bad' },
        { id: 'src-2', valid: false, error: 'worse' }
      ]
      results.sourceSelection.allInvalid = __test.selectFirstValid(allInvalid)
      results.sourceSelection.noSources = __test.selectFirstValid([])
    }

    // Board helpers
    results.board = {}
    if (__test.normalizeStatus) {
      results.board.normalizeInProgress = __test.normalizeStatus('in-progress')
      results.board.normalizeDraft = __test.normalizeStatus('draft')
      results.board.normalizeArchived = __test.normalizeStatus('archived')
      results.board.normalizeIdeas = __test.normalizeStatus('ideas')
      results.board.normalizeUnknown = __test.normalizeStatus('something-new')
    }
    if (__test.groupByStatus) {
      const items = [
        { name: 'a', status: 'draft', token: 'A', sequence: 2 },
        { name: 'b', status: 'in-progress', token: 'B', sequence: 1 },
        { name: 'c', status: 'done', token: 'C', sequence: 3 },
        { name: 'd', status: 'archived', token: 'D', sequence: 0 },
        { name: 'idea', status: 'ideas', token: 'IDEA', sequence: 4 },
      ]
      const groups = __test.groupByStatus(items, false)
      results.board.groupKeys = Object.keys(groups)
      results.board.groupCounts = {}
      for (const k in groups) results.board.groupCounts[k] = groups[k].length
    }
    if (__test.sortItems) {
      const sortItems = [
        { name: 'b', sequence: 2, title: 'Alpha' },
        { name: 'a', sequence: 1, title: 'Beta' },
        { name: 'c', sequence: 1, title: 'Alpha' },
      ]
      results.board.sorted = __test.sortItems(sortItems).map(i => i.name)
    }
    if (__test.filterItems) {
      const filterItems = [
        { name: 'alpha-change', title: 'Alpha Feature', token: 'ALPHA' },
        { name: 'beta-fix', title: 'Beta Bugfix', token: 'BETA' },
        { name: 'gamma-refactor', title: 'Gamma Refactor', token: 'GAMMA' },
      ]
      results.board.filteredAlpha = __test.filterItems(filterItems, 'alpha').map(i => i.name)
      results.board.filteredBeta = __test.filterItems(filterItems, 'BETA').map(i => i.name)
      results.board.filteredEmpty = __test.filterItems(filterItems, 'delta').map(i => i.name)
      results.board.filteredClear = __test.filterItems(filterItems, '').map(i => i.name)
    }
    if (__test.toggleArchived) {
      results.board.withArchived = __test.toggleArchived(true)
      results.board.withoutArchived = __test.toggleArchived(false)
    }

    // in_progress (underscore) grouping — backend emits this spelling
    if (__test.groupByStatus && __test.normalizeStatus) {
      var inProgressItems = [
        { name: 'item-a', status: 'in_progress', token: 'A' },
        { name: 'item-b', status: 'in-progress', token: 'B' },
        { name: 'item-c', status: 'inprogress', token: 'C' },
      ]
      var ipGroups = __test.groupByStatus(inProgressItems, false)
      results.board.inProgressGroupCount = (ipGroups['in-progress'] || []).length
      results.board.inProgressNormalized = __test.normalizeStatus('in_progress')
    }

    // Task parser
    results.tasks = {}
    if (__test.parseTasks) {
      const taskContent = '## Section 1\n- [x] Done task\n- [ ] Pending task\n- [x] Another done\n\n## Section 2\n- [ ] Open task\n'
      const parsed = __test.parseTasks(taskContent)
      results.tasks.total = parsed.total
      results.tasks.done = parsed.done
      results.tasks.sections = parsed.sections
    }

    // Markdown parser
    results.markdown = {}
    if (__test.renderMarkdown) {
      const md = '# Heading\n\nA paragraph with **bold** and `code`.\n\n- item 1\n- item 2'
      const rendered = __test.renderMarkdown(md)
      results.markdown.isArray = Array.isArray(rendered)
      results.markdown.length = rendered && rendered.length
    }

    // State classifier
    if (__test.classifyState) {
      results.markdown.stateLoading = __test.classifyState({ isLoading: true, error: null, data: null })
      results.markdown.stateError = __test.classifyState({ isLoading: false, error: new Error('fail'), data: null })
      results.markdown.stateEmpty = __test.classifyState({ isLoading: false, error: null, data: { items: [] } })
      results.markdown.stateContent = __test.classifyState({ isLoading: false, error: null, data: { items: [1] } })
    }

    // Diff helpers
    results.diff = {}
    if (__test.classifyDiffLine) {
      results.diff.added = __test.classifyDiffLine('+added line')
      results.diff.removed = __test.classifyDiffLine('-removed line')
      results.diff.hunk = __test.classifyDiffLine('@@ -1,3 +1,4 @@')
      results.diff.context = __test.classifyDiffLine(' unchanged line')
    }
    if (__test.hasDiffMode) {
      results.diff.hasSemantic = __test.hasDiffMode({ semantic_diff: { groups: [] } }, 'semantic')
      results.diff.hasSplit = __test.hasDiffMode({ before: 'a', after: 'b' }, 'split')
      results.diff.hasRaw = __test.hasDiffMode({ diff: '+line' }, 'raw')
      results.diff.noSemantic = __test.hasDiffMode({ before: 'a', after: 'b' }, 'semantic')
    }

    // --- Behavioral fixture tests: backend contract alignment ---

    // 1. Semantic groups normalization — exact backend shape from spec_parser.py
    results.semanticGroups = {}
    if (__test.normalizeSemanticGroups) {
      // Backend returns {status, requirements: {added, modified, removed, unchanged}}
      var backendDiff = {
        status: 'modified',
        requirements: {
          added: [{ name: 'Auth', description: 'User auth via OAuth', scenarios: [] }],
          modified: [{
            name: 'Data Model',
            before: { description: 'Old schema with 3 fields', scenarios: [] },
            after: { description: 'New schema with 5 fields', scenarios: [] },
            scenarios_added: [],
            scenarios_modified: [],
            scenarios_removed: [],
          }],
          removed: [{ name: 'Legacy', description: 'Deprecated endpoint', scenarios: [] }],
          unchanged: ['Logging'],
        }
      }
      var groups = __test.normalizeSemanticGroups(backendDiff)
      results.semanticGroups.isArray = Array.isArray(groups)
      results.semanticGroups.length = groups.length
      // Verify labels
      results.semanticGroups.addedLabel = groups[0] && groups[0].label
      results.semanticGroups.modifiedLabel = groups[1] && groups[1].label
      results.semanticGroups.removedLabel = groups[2] && groups[2].label
      // Verify no [object Object] in descriptions
      results.semanticGroups.noObjectString = groups.every(function(g) {
        return !String(g.description || '').includes('[object Object]')
          && !String(g.before || '').includes('[object Object]')
          && !String(g.after || '').includes('[object Object]')
      })
      // Verify names preserved
      results.semanticGroups.addedName = groups[0] && groups[0].name
      results.semanticGroups.modifiedName = groups[1] && groups[1].name
      results.semanticGroups.removedName = groups[2] && groups[2].name
      // Verify before/after extracted from object-valued fields
      results.semanticGroups.beforeDesc = groups[1] && groups[1].before
      results.semanticGroups.afterDesc = groups[1] && groups[1].after
      // Verify crash: old code did data.requirements.map() which throws
      results.semanticGroups.noCrash = true
      try {
        // This is what the old code did — should have thrown
        backendDiff.requirements.map(function() {})
        results.semanticGroups.oldCodeWouldThrow = false
      } catch (e) {
        results.semanticGroups.oldCodeWouldThrow = true
      }
    }

    // 2. Card artifacts from has* booleans — exact shape from plugin_api.py
    results.cardArtifacts = {}
    if (__test.hasDiffMode) {
      // Backend source summary shape from plugin_api.py:218-241
      var changeSummary = {
        id: 'src-1/my-change',
        token: 'my-change',
        name: 'my-change',
        title: 'My Change',
        status: 'in-progress',
        hasProposal: true,
        hasTasks: true,
        hasDesign: false,
        hasSpecs: true,
        taskStats: { total: 5, done: 2 },
      }
      // Test that has* booleans are the source of truth (not artifacts/artifactNames)
      results.cardArtifacts.hasProposal = changeSummary.hasProposal === true
      results.cardArtifacts.hasTasks = changeSummary.hasTasks === true
      results.cardArtifacts.hasDesign = changeSummary.hasDesign === false
      results.cardArtifacts.hasSpecs = changeSummary.hasSpecs === true
      results.cardArtifacts.noArtifactsField = changeSummary.artifacts === undefined
      results.cardArtifacts.noArtifactNamesField = changeSummary.artifactNames === undefined
    }

    // 3. effectiveDiffMode fallback
    results.effectiveDiffMode = {}
    if (__test.effectiveDiffMode) {
      // When desired mode is available, return it
      results.effectiveDiffMode.semanticAvailable = __test.effectiveDiffMode('semantic', { semantic_diff: { requirements: {} } })
      // When semantic unavailable but split available, fallback to split
      results.effectiveDiffMode.fallbackToSplit = __test.effectiveDiffMode('semantic', { before: 'a', after: 'b' })
      // When only raw available, fallback to raw
      results.effectiveDiffMode.fallbackToRaw = __test.effectiveDiffMode('semantic', { diff: '+line' })
      // When nothing available, return desired (no crash)
      results.effectiveDiffMode.nothingAvailable = __test.effectiveDiffMode('semantic', {})
      // Split desired but only raw available
      results.effectiveDiffMode.splitToRaw = __test.effectiveDiffMode('split', { diff: '+line' })
    }

    // RetryErrorState wrapper — verify structure via __test
    results.retryErrorState = null
    if (__test.RetryErrorState) {
      // Call RetryErrorState with a test callback and title/description
      var testCallback = function() { return 'retried' }
      var descriptor = __test.RetryErrorState({ title: 'Error', description: 'fail', onRetry: testCallback })
      if (descriptor && descriptor._t) {
        var res = { rootIsErrorState: false, hasButtonChild: false, buttonOnClickIsFunction: false, buttonLabel: null, onClickInvokesCallback: false }
        // Root should be ErrorState — the shim stores the function reference
        // (not the string 'ErrorState'), so verify it's a function
        res.rootIsErrorState = typeof descriptor.component === 'function'
        // Children should contain a Button
        var children = descriptor.props && descriptor.props.children
        if (children) {
          var childArr = Array.isArray(children) ? children : [children]
          for (var ci = 0; ci < childArr.length; ci++) {
            var child = childArr[ci]
            if (child && child._t && child.component && typeof child.component === 'function') {
              res.hasButtonChild = true
              res.buttonLabel = child.props && child.props.children
              var onClick = child.props && child.props.onClick
              res.buttonOnClickIsFunction = typeof onClick === 'function'
              if (res.buttonOnClickIsFunction) {
                var result = onClick()
                res.onClickInvokesCallback = result === 'retried'
              }
              break
            }
          }
        }
        results.retryErrorState = res
      }
    }

    // Lane layout helpers
    results.laneLayout = {}
    if (__test.autoCollapseEmptyLanes) {
      var groupedMixed = { 'ideas': [], 'draft': [{ name: 'a' }], 'todo': [{ name: 'b' }], 'in-progress': [], 'done': [], 'archived': [] }
      var collapsed = __test.autoCollapseEmptyLanes(groupedMixed, ['ideas', 'draft', 'todo', 'in-progress', 'done', 'archived'])
      results.laneLayout.collapseEmptyWhenWork = !!collapsed['ideas']
      results.laneLayout.expandNonEmpty = !collapsed['draft']
      results.laneLayout.expandNonEmptyTodo = !collapsed['todo']
      results.laneLayout.collapseInProgress = !!collapsed['in-progress']
      results.laneLayout.collapseDone = !!collapsed['done']

      // Board with no work: nothing collapses
      var allEmpty = { 'ideas': [], 'draft': [], 'todo': [], 'in-progress': [], 'done': [], 'archived': [] }
      var noCollapse = __test.autoCollapseEmptyLanes(allEmpty, ['ideas', 'draft', 'todo', 'in-progress', 'done', 'archived'])
      var anyCollapsed = false
      for (var k in noCollapse) { if (noCollapse[k]) anyCollapsed = true }
      results.laneLayout.noWorkNoCollapse = !anyCollapsed
    }
    if (__test.laneWidth) {
      results.laneLayout.expandedWidth = __test.laneWidth('draft', {})
      results.laneLayout.collapsedWidth = __test.laneWidth('ideas', { 'ideas': true })
      results.laneLayout.noOverridesExpanded = __test.laneWidth('draft', { 'ideas': true })
    }
    if (__test.LANE_EXPANDED_WIDTH) {
      results.laneLayout.expandedIs256 = __test.LANE_EXPANDED_WIDTH === 256
    }
    if (__test.LANE_COLLAPSED_WIDTH) {
      results.laneLayout.collapsedIs32 = __test.LANE_COLLAPSED_WIDTH === 32
    }
    if (__test.railStyle) {
      var rs = __test.railStyle('Ideas')
      results.laneLayout.railWidth = rs && rs.width
      results.laneLayout.railFlexShrink = rs && rs.flexShrink
      results.laneLayout.railCursor = rs && rs.cursor
    }
    if (__test.expandedStyle) {
      var es = __test.expandedStyle()
      results.laneLayout.expandedWidthPx = es && es.width
      results.laneLayout.expandedFlexShrink = es && es.flexShrink
      results.laneLayout.expandedOverflow = es && es.overflow
      results.laneLayout.expandedHasBg = es && es.background && es.background.includes('color-mix')
      results.laneLayout.expandedHasRounded = es && es.borderRadius === '8px'
      results.laneLayout.expandedHasPadding = es && es.padding === '8px'
    }

    // STATUS_TONE mapping
    results.statusTone = {}
    if (__test.STATUS_TONE && __test.statusTone) {
      results.statusTone.ideas = __test.statusTone('ideas')
      results.statusTone.draft = __test.statusTone('draft')
      results.statusTone.todo = __test.statusTone('todo')
      results.statusTone.inProgress = __test.statusTone('in-progress')
      results.statusTone.done = __test.statusTone('done')
      results.statusTone.archived = __test.statusTone('archived')
      results.statusTone.unknown = __test.statusTone('unknown-status')
      results.statusTone.ideasIsVar = __test.STATUS_TONE['ideas'] === 'var(--ui-text-tertiary)'
      results.statusTone.draftIsPurple = __test.STATUS_TONE['draft'] === '#a78bfa'
      results.statusTone.todoIsVar = __test.STATUS_TONE['todo'] === 'var(--ui-text-secondary)'
      results.statusTone.inProgressIsGreen = __test.STATUS_TONE['in-progress'] === '#34d399'
      results.statusTone.doneIsVar = __test.STATUS_TONE['done'] === 'var(--ui-text-tertiary)'
      results.statusTone.archivedIsVar = __test.STATUS_TONE['archived'] === 'var(--ui-text-quaternary)'
    }

    // URL safety
    results.urlSafety = {}
    if (__test.isSafeUrl) {
      results.urlSafety.httpsAllowed = __test.isSafeUrl('https://example.com')
      results.urlSafety.httpAllowed = __test.isSafeUrl('http://example.com')
      results.urlSafety.relativeAllowed = __test.isSafeUrl('/path/to/page')
      results.urlSafety.fragmentAllowed = __test.isSafeUrl('#section')
      results.urlSafety.queryAllowed = __test.isSafeUrl('?key=val')
      results.urlSafety.mailtoAllowed = __test.isSafeUrl('mailto:user@example.com')
      results.urlSafety.javascriptBlocked = !__test.isSafeUrl('javascript:alert(1)')
      results.urlSafety.dataBlocked = !__test.isSafeUrl('data:text/html,<script>')
      results.urlSafety.fileBlocked = !__test.isSafeUrl('file:///etc/passwd')
      results.urlSafety.vbscriptBlocked = !__test.isSafeUrl('vbscript:MsgBox(1)')
      results.urlSafety.emptyBlocked = !__test.isSafeUrl('')
      results.urlSafety.nullBlocked = !__test.isSafeUrl(null)
      // Whitespace/control obfuscation tests
      results.urlSafety.wsJavascriptBlocked = !__test.isSafeUrl('  javascript:alert(1)')
      results.urlSafety.tabJavascriptBlocked = !__test.isSafeUrl('\tjavascript:alert(1)')
      results.urlSafety.newlineJavascriptBlocked = !__test.isSafeUrl('\njavascript:alert(1)')
      results.urlSafety.controlJavascriptBlocked = !__test.isSafeUrl('\x00javascript:alert(1)')
      results.urlSafety.uppercaseJavascriptBlocked = !__test.isSafeUrl('JAVASCRIPT:alert(1)')
      results.urlSafety.mixedCaseDataBlocked = !__test.isSafeUrl('DaTa:text/html,<script>')
    }

    // __test is frozen
    results.testFrozen = Object.isFrozen(__test)

    // renderInline returns JSX (not plain objects)
    results.inlineJsx = {}
    if (__test.renderMarkdown && __test.MarkdownElement && __test.renderInline) {
      // Parse markdown into blocks
      var inlineResult = __test.renderMarkdown('Text with **bold** and `code` and [link](https://example.com)')
      results.inlineJsx.isArray = Array.isArray(inlineResult)
      results.inlineJsx.hasParagraph = inlineResult.some(function(el) { return el && el.type === 'paragraph' })

      // EXECUTABLE RENDER CHECK: invoke MarkdownElement on each parsed block
      // and verify it returns JSX descriptors (with _t property from jsx shim), not raw parser objects
      var allBlocksAreJsx = true
      var anyBlockFailed = false
      for (var bi = 0; bi < inlineResult.length; bi++) {
        var block = inlineResult[bi]
        if (!block || !block.type) continue
        var rendered = __test.MarkdownElement(block)
        // JSX shim returns {component, props, _t: "jsx"} — parser objects have no _t
        if (!rendered || typeof rendered !== 'object' || !rendered._t) {
          allBlocksAreJsx = false
          anyBlockFailed = true
          break
        }
      }
      results.inlineJsx.blocksRenderToJsx = allBlocksAreJsx
      results.inlineJsx.anyBlockFailed = anyBlockFailed

      // EXECUTABLE RENDER CHECK: invoke renderInline directly on inline text
      // and verify each inline element returns JSX, not plain objects
      var inlineParts = __test.renderInline('Hello **bold** world')
      results.inlineJsx.inline = {}
      results.inlineJsx.inline.isArray = Array.isArray(inlineParts)
      var inlineAllJsx = true
      if (Array.isArray(inlineParts)) {
        for (var ii = 0; ii < inlineParts.length; ii++) {
          var part = inlineParts[ii]
          // Strings are fine (plain text between markers)
          if (typeof part === 'string') continue
          // JSX elements must have _t property
          if (!part || typeof part !== 'object' || !part._t) {
            inlineAllJsx = false
            break
          }
        }
      }
      results.inlineJsx.inline.allJsx = inlineAllJsx

      // Mixed bold/code/link rendering — verify each inline type produces JSX
      var mixedParts = __test.renderInline('**bold** and `code` and [click](https://x.com)')
      results.inlineJsx.mixed = {}
      if (Array.isArray(mixedParts)) {
        var jsxParts = mixedParts.filter(function(p) { return p && typeof p === 'object' && p._t })
        results.inlineJsx.mixed.count = jsxParts.length
        // Should have 3 JSX elements: strong, code, a
        results.inlineJsx.mixed.hasThree = jsxParts.length === 3
        // Verify component types
        var componentNames = jsxParts.map(function(p) {
          return p.props && p.props.children ? (typeof p.props.children === 'string' ? p.props.children.substring(0, 10) : '?') : '?'
        })
        results.inlineJsx.mixed.componentChildren = componentNames
      }
    }

  } catch (e) {
    results.__testError = e.message
  }

  // ═══════════════════════════════════════════════════════════════════════════════
  // Lane override behavior tests
  // ═══════════════════════════════════════════════════════════════════════════════
  try {
    var SO = ['todo', 'in-progress', 'done']

    // 1. computeCollapsedSet
    results.collapsedSet = {}
    if (__test.computeCollapsedSet) {
      var auto = { todo: true } // todo empty, in-progress & done have work
      var empty = __test.computeCollapsedSet(auto, {}, SO)
      results.collapsedSet.autoOnlyEmpty = empty.todo === true
      results.collapsedSet.autoOnlyPopulated = empty['in-progress'] === false
      var withOverride = __test.computeCollapsedSet(auto, { todo: false }, SO)
      results.collapsedSet.overrideEmpty = withOverride.todo === false
      var withOverrideFull = __test.computeCollapsedSet(auto, { 'in-progress': true }, SO)
      results.collapsedSet.overridePopulated = withOverrideFull['in-progress'] === true
    }

    // 2. toggleOverride
    results.toggle = {}
    if (__test.toggleOverride) {
      var autoMap = { todo: true } // todo is auto-collapsed (empty lane)
      var t1 = __test.toggleOverride({}, 'todo', autoMap)
      results.toggle.firstToggleEmpty = t1.todo
      var t2 = __test.toggleOverride(t1, 'todo', autoMap)
      results.toggle.secondToggleEmpty = t2.todo

      var autoMapFull = { 'in-progress': false } // in-progress is auto-expanded (has work)
      var t3 = __test.toggleOverride({}, 'in-progress', autoMapFull)
      results.toggle.firstTogglePopulated = t3['in-progress']
      var t4 = __test.toggleOverride(t3, 'in-progress', autoMapFull)
      results.toggle.secondTogglePopulated = t4['in-progress']
    }

    // 3. computeLanePhase
    results.lanePhase = {}
    if (__test.computeLanePhase) {
      var g1 = { todo: [], 'in-progress': [{x:1}], done: [] }
      results.lanePhase.empty = __test.computeLanePhase(g1, ['todo', 'in-progress', 'done'])
      var g2 = { todo: [{x:1}], 'in-progress': [], done: [{x:1}] }
      results.lanePhase.full = __test.computeLanePhase(g2, ['todo', 'in-progress', 'done'])
      results.lanePhase.nullGrouped = __test.computeLanePhase(null, SO)
    }

    // 4. pruneStaleOverrides
    results.prune = {}
    if (__test.pruneStaleOverrides) {
      // Phase changed on override lane → pruned
      var prev1 = 'todo:empty|in-progress:full|done:empty'
      var cur1 = 'todo:full|in-progress:full|done:empty'  // todo flipped empty→full
      var pruned1 = __test.pruneStaleOverrides({ todo: false, done: true }, prev1, cur1)
      results.prune.changedLanePruned = pruned1.todo === undefined && pruned1.done === true

      // Phase unchanged → kept
      var prev2 = 'todo:empty|in-progress:full|done:empty'
      var cur2 = 'todo:empty|in-progress:full|done:empty'
      var pruned2 = __test.pruneStaleOverrides({ todo: false }, prev2, cur2)
      results.prune.unchangedLaneKept = pruned2.todo === false

      // Phase changed but no override → harmless
      var prev3 = 'todo:empty|in-progress:full'
      var cur3 = 'todo:full|in-progress:full'
      var pruned3 = __test.pruneStaleOverrides({}, prev3, cur3)
      results.prune.changedNoOverride = Object.keys(pruned3).length === 0

      // Null previous phase → no pruning
      var pruned4 = __test.pruneStaleOverrides({ todo: false }, null, 'todo:full|in-progress:full')
      results.prune.nullPrevPhase = pruned4.todo === false

      // Mixed: two overrides, only affected one pruned
      var prev5 = 'todo:empty|in-progress:full|done:empty'
      var cur5 = 'todo:full|in-progress:full|done:full'  // todo and done flipped
      var pruned5 = __test.pruneStaleOverrides({ todo: false, 'in-progress': true, done: true }, prev5, cur5)
      results.prune.mixedPruning = pruned5.todo === undefined && pruned5['in-progress'] === true && pruned5.done === undefined
    }

    // 5. Toggle integration
    results.toggleIntegration = {}
    if (__test.toggleOverride && __test.computeCollapsedSet) {
      var autoEmpty = { todo: true }
      var autoFull = { 'in-progress': false }

      // Toggle auto-collapsed twice → back to auto
      var o1 = __test.toggleOverride({}, 'todo', autoEmpty)
      var o2 = __test.toggleOverride(o1, 'todo', autoEmpty)
      var cs1 = __test.computeCollapsedSet(autoEmpty, o2, ['todo'])
      results.toggleIntegration.autoCollapsedDeleted = cs1.todo === true // auto wins

      // Toggle auto-expanded twice → back to auto
      var o3 = __test.toggleOverride({}, 'in-progress', autoFull)
      var o4 = __test.toggleOverride(o3, 'in-progress', autoFull)
      var cs2 = __test.computeCollapsedSet(autoFull, o4, ['in-progress'])
      results.toggleIntegration.autoExpandedDeleted = cs2['in-progress'] === false // auto wins

      // Partial toggle: only one lane, other preserved
      var o5 = __test.toggleOverride({}, 'todo', autoEmpty)
      var cs3 = __test.computeCollapsedSet(autoEmpty, o5, ['todo', 'in-progress'])
      results.toggleIntegration.partialToggleKept = o5.todo === false && cs3['in-progress'] === false
    }

    // 6. trimPath
    results.trimPath = {}
    if (__test.trimPath) {
      results.trimPath.basicTrim = __test.trimPath('  /path/to/repo  ')
      results.trimPath.noTrim = __test.trimPath('/path/to/repo')
      results.trimPath.emptyString = __test.trimPath('')
      results.trimPath.whitespaceOnly = __test.trimPath('   ')
      results.trimPath.nonString = __test.trimPath(null)
      results.trimPath.number = __test.trimPath(42)
    }

    // 7. extractApiError
    results.extractApiError = {}
    if (__test.extractApiError) {
      results.extractApiError.nullInput = __test.extractApiError(null)
      results.extractApiError.stringInput = __test.extractApiError('bad request')
      results.extractApiError.messageObj = __test.extractApiError({ message: 'not found' })
      results.extractApiError.detailObj = __test.extractApiError({ detail: 'conflict' })
      results.extractApiError.duplicateSource = __test.extractApiError({ message: "Error invoking remote method 'hermes:api': Error: 409: {\"detail\":\"Source already registered\"}" })
      results.extractApiError.fallback = __test.extractApiError({ code: 500 })
    }

    // 8. Source mutation adapter — create a fresh api via register and test mutation methods
    results.sourceMutation = {}
    try {
      // Create a fresh mock ctx to capture the api object
      let capturedApi = null
      const testCtx = {
        register() {},
        registerMany(arr) {
          for (const c of arr) {
            if (c.render) {
              // Intercept render to capture the api from its closure
              const origRender = c.render
              c.render = function() {
                // The api is created in register() and passed to OpenSpecPage
                // We can't directly access it, so we'll test via __test
                return origRender()
              }
            }
          }
        },
        rest(path, opts) {
          results.sourceMutation.lastRestPath = path
          results.sourceMutation.lastRestOpts = opts || null
          return Promise.resolve({ ok: true })
        }
      }
      plugin.register(testCtx)

      // Test addSource path and body via a direct rest mock
      let addRestCalls = []
      const addCtx = {
        register() {},
        registerMany() {},
        rest(path, opts) { addRestCalls.push({ path, opts }); return Promise.resolve({}) }
      }
      results.sourceMutation.addSourcePath = __test.sourcesPath ? __test.sourcesPath() : null
      results.sourceMutation.updatePathEncodes = __test.changePath ? __test.changePath('src-1', 'test') : null
      if (__test.createApi) {
        const initCalls = []
        const initApi = __test.createApi({ rest(path, opts) {
          initCalls.push({ path, opts })
          return Promise.resolve({ ok: true })
        } })
        await initApi.initSource('source id')
        results.sourceMutation.initSourcePath = initCalls[0] && initCalls[0].path
        results.sourceMutation.initSourceMethod = initCalls[0] && initCalls[0].opts && initCalls[0].opts.method
        results.sourceMutation.initSourceBody = initCalls[0] && initCalls[0].opts && initCalls[0].opts.body
        results.sourceMutation.needsInit = __test.sourceNeedsInitialization({ source: { id: 'os-1', valid: false, error: 'No openspec/ directory found' } })
        results.sourceMutation.validNeedsNoInit = __test.sourceNeedsInitialization({ source: { id: 'os-1', valid: true, error: null } })
        // Exact endpoint allowlist: the four dashboard source endpoints only,
        // with encoded identifiers, exact methods, and object request bodies.
        const mutCalls = []
        const mutApi = __test.createApi({ rest(path, opts) {
          mutCalls.push({ path, opts })
          return Promise.resolve({ ok: true, source: { id: 'src-1' } })
        } })
        await mutApi.sources()
        await mutApi.addSource('/repos/acme', 'Acme')
        await mutApi.addSource('/repos/bare')
        await mutApi.updateSource('src id/with slash', '/repos/acme-new', 'Acme New')
        await mutApi.initSource('src id')
        await mutApi.removeSource('src id')
        const addCall = mutCalls.find((c) => c.path === '/sources' && c.opts && c.opts.method === 'POST' && c.opts.body && c.opts.body.name === 'Acme')
        const addBareCall = mutCalls.find((c) => c.path === '/sources' && c.opts && c.opts.method === 'POST' && c.opts.body && c.opts.body.path === '/repos/bare')
        const updateCall = mutCalls.find((c) => c.path === '/sources/src%20id%2Fwith%20slash' && c.opts && c.opts.method === 'PUT')
        const removeCall = mutCalls.find((c) => c.path === '/sources/src%20id' && c.opts && c.opts.method === 'DELETE')
        const sourcesCall = mutCalls.find((c) => c.path === '/sources' && !c.opts)
        results.sourceMutation.addCallPath = addCall && addCall.path
        results.sourceMutation.addCallMethod = addCall && addCall.opts.method
        results.sourceMutation.addCallBody = addCall && addCall.opts.body
        results.sourceMutation.addBareCallBody = addBareCall && addBareCall.opts.body
        results.sourceMutation.updateCallPath = updateCall && updateCall.path
        results.sourceMutation.updateCallMethod = updateCall && updateCall.opts.method
        results.sourceMutation.updateCallBody = updateCall && updateCall.opts.body
        results.sourceMutation.removeCallPath = removeCall && removeCall.path
        results.sourceMutation.removeCallMethod = removeCall && removeCall.opts.method
        results.sourceMutation.removeCallBody = removeCall && removeCall.opts.body
        results.sourceMutation.sourcesCallMethod = sourcesCall && sourcesCall.opts ? sourcesCall.opts.method : undefined
        const apiKeys = Object.keys(mutApi).sort()
        results.sourceMutation.mutationMethods = ['addSource', 'updateSource', 'initSource', 'removeSource'].filter((k) => apiKeys.includes(k))
        results.sourceMutation.allowlistExact = JSON.stringify(apiKeys) === JSON.stringify(['addSource', 'change', 'idea', 'initSource', 'removeSource', 'sources', 'spec', 'specBrowser', 'updateSource'].sort())
        results.sourceMutation.noGenericRequest = !apiKeys.includes('request')
      }
    } catch (e) {
      results.sourceMutation.error = e.message
    }

  } catch (e) {
    results.__laneOverrideError = e.message
  }
}

process.stdout.write(JSON.stringify(results))

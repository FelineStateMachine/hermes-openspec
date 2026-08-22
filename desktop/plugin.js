/**
 * OpenSpec Desktop runtime plugin — source registry + project surface.
 *
 * Registers /openspec route + sidebar nav entry. Provides source selector,
 * work board (ideas, changes by status), change/idea detail dialogs,
 * current specs browser, worktree diff views, and source management
 * (add/edit/remove) via the existing backend CRUD routes.
 *
 * Packaging: single uncompiled ESM file. Runtime loader scans
 * ~/.hermes/plugins/openspec/desktop/plugin.js.
 */

import {
  Badge, Button, cn, Codicon, CopyButton, Dialog, DialogContent, EmptyState, ErrorState,
  Input, Loader, ROUTES_AREA, SearchField, Select,
  SelectContent, SelectItem, SelectTrigger, SelectValue,
  SegmentedControl, SIDEBAR_NAV_AREA, Tabs, TabsList, TabsTrigger, useQuery
} from '@hermes/plugin-sdk'
import React from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

var SOURCE_TRIGGER_HOVER_CSS = '[data-openspec-source-trigger].desktop-input-chrome { background-color: var(--chrome-action-hover) !important; } [data-openspec-source-trigger].desktop-input-chrome:hover { background-color: var(--chrome-action-hover) !important; }'

// ═══════════════════════════════════════════════════════════════════════════════
// Pure helpers — exported as __test for headless verification
// ═══════════════════════════════════════════════════════════════════════════════

function sourcesPath() { return '/sources' }

function changePath(sourceId, name) {
  return '/sources/' + encodeURIComponent(sourceId) + '/changes/' + encodeURIComponent(name)
}

function ideaPath(sourceId, name) {
  return '/sources/' + encodeURIComponent(sourceId) + '/ideas/' + encodeURIComponent(name)
}

function specBrowserPath(sourceId, opts) {
  var base = '/sources/' + encodeURIComponent(sourceId) + '/spec-browser'
  if (opts && opts.dirty) return base + '?dirty=true'
  return base
}

function specPath(sourceId, path) {
  return '/sources/' + encodeURIComponent(sourceId) + '/specs?path=' + encodeURIComponent(path)
}

function selectFirstValid(sources) {
  if (!sources || sources.length === 0) return null
  var valid = sources.filter(function(s) { return s.valid !== false })
  if (valid.length > 0) return valid[0]
  return sources[0]
}

function normalizeStatus(status) {
  var s = String(status || '').toLowerCase()
  if (s === 'in-progress' || s === 'inprogress' || s === 'in_progress') return 'in-progress'
  if (s === 'ideas') return 'ideas'
  if (s === 'draft') return 'draft'
  if (s === 'todo') return 'todo'
  if (s === 'done') return 'done'
  if (s === 'archived') return 'archived'
  return 'todo'
}

var STATUS_ORDER = ['ideas', 'draft', 'todo', 'in-progress', 'done', 'archived']

function groupByStatus(items, showArchived) {
  var groups = {}
  var order = showArchived ? STATUS_ORDER : STATUS_ORDER.filter(function(s) { return s !== 'archived' })
  for (var i = 0; i < order.length; i++) groups[order[i]] = []
  for (var j = 0; j < (items || []).length; j++) {
    var item = items[j]
    var status = normalizeStatus(item.status || item.state || item.phase)
    if (!showArchived && status === 'archived') continue
    if (!groups[status]) groups[status] = []
    groups[status].push(item)
  }
  return groups
}

function normalizeSequencePosition(sequence) {
  var position = sequence && typeof sequence === 'object' ? sequence.position : sequence
  return typeof position === 'number' && Number.isFinite(position) ? position : null
}

function sortItems(items) {
  return (items || []).slice().sort(function(a, b) {
    var sa = normalizeSequencePosition(a.sequence)
    var sb = normalizeSequencePosition(b.sequence)
    if (sa == null) sa = 9999
    if (sb == null) sb = 9999
    if (sa !== sb) return sa - sb
    var ta = (a.title || a.name || '').toLowerCase()
    var tb = (b.title || b.name || '').toLowerCase()
    if (ta < tb) return -1
    if (ta > tb) return 1
    return 0
  })
}

function filterItems(items, query) {
  if (!query) return items || []
  var q = String(query).toLowerCase()
  return (items || []).filter(function(item) {
    var title = String(item.title || item.name || '').toLowerCase()
    var token = String(item.token || '').toLowerCase()
    var name = String(item.name || '').toLowerCase()
    return title.includes(q) || token.includes(q) || name.includes(q)
  })
}

function toggleArchived(current) { return !current }

function stripFrontmatter(content) {
  if (!content) return content
  return content.replace(/^---\s*\n[\s\S]*?\n---\s*\n?/, '')
}

// ═══════════════════════════════════════════════════════════════════════════════
// Resolver-safe identity helpers — pure, testable, canonical-aligned
// ═══════════════════════════════════════════════════════════════════════════════

function buildSourceReference(source, allSources) {
  if (!source) return ''
  var name = String(source.name || '').trim()
  if (name) {
    var count = 0
    for (var i = 0; i < (allSources || []).length; i++) {
      var other = allSources[i]
      if (other && String(other.name || '').trim().toLowerCase() === name.toLowerCase()) count++
    }
    if (count === 1) return name
  }
  var token = String(source.token || '').trim()
  if (token) return token
  var id = String(source.id || '').trim()
  if (id) return id
  return ''
}

function buildItemReference(source, item, allSources) {
  var sourceRef = buildSourceReference(source, allSources)
  var token = item && item.token ? String(item.token).trim() : ''
  if (!sourceRef || !token) return ''
  return sourceRef + '/' + token
}

function hasUniqueItemToken(item, allItems) {
  var token = item && item.token ? String(item.token).trim() : ''
  if (!token) return false
  var count = 0
  for (var i = 0; i < (allItems || []).length; i++) {
    var other = allItems[i]
    if (other && String(other.token || '').trim() === token) count++
  }
  return count === 1
}

function createSessionStore() {
  return { selectedSourceId: null, showArchived: true }
}

function resolveRetainedSource(sources, retainedId) {
  if (!sources || sources.length === 0) return null
  if (retainedId != null && retainedId !== '') {
    for (var i = 0; i < sources.length; i++) {
      if (sources[i].id === retainedId) return retainedId
    }
  }
  var fallback = selectFirstValid(sources)
  return fallback ? fallback.id : null
}

function detailTitle(loaded, summary, item, kind) {
  if (loaded && loaded.title) return loaded.title
  if (summary && summary.title) return summary.title
  if (item && item.name) return item.name
  return kind === 'idea' ? 'Untitled idea' : 'Untitled change'
}

function detailSecondaryName(loaded, summary) {
  if (loaded && loaded.name) return loaded.name
  if (summary && summary.name) return summary.name
  return ''
}

function ideaSecondaryName(name) {
  if (!name) return ''
  return String(name).replace(/\.md$/i, '') + '.md'
}

function handleActivateKey(e, action) {
  if (!e) return
  if (e.key === 'Enter' || e.key === ' ') {
    if (typeof e.preventDefault === 'function') e.preventDefault()
    if (action) action()
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Lane override helpers — pure, testable, canonical-aligned
// ═══════════════════════════════════════════════════════════════════════════════

function computeCollapsedSet(autoCollapsed, manualOverrides, statusOrder) {
  var result = {}
  for (var i = 0; i < statusOrder.length; i++) {
    var s = statusOrder[i]
    if (manualOverrides[s] !== undefined) {
      result[s] = manualOverrides[s]
    } else {
      result[s] = !!autoCollapsed[s]
    }
  }
  return result
}

function toggleOverride(prev, status, autoCollapsed) {
  var next = Object.assign({}, prev)
  var auto = !!autoCollapsed[status]
  if (next[status] !== undefined) {
    delete next[status]
  } else {
    next[status] = !auto
  }
  return next
}

function computeLanePhase(grouped, statusOrder) {
  if (!grouped) return null
  var parts = []
  for (var i = 0; i < statusOrder.length; i++) {
    var s = statusOrder[i]
    var items = grouped[s] || []
    parts.push(s + ':' + (items.length === 0 ? 'empty' : 'full'))
  }
  return parts.join('|')
}

function pruneStaleOverrides(prevOverrides, prevPhase, lanePhase) {
  if (prevPhase === null || lanePhase === null || lanePhase === prevPhase) {
    return prevOverrides
  }
  var before = {}
  var prevParts = prevPhase.split('|')
  for (var i = 0; i < prevParts.length; i++) {
    var kv = prevParts[i].split(':')
    before[kv[0]] = kv[1]
  }
  var next = Object.assign({}, prevOverrides)
  var changed = false
  var curParts = lanePhase.split('|')
  for (var j = 0; j < curParts.length; j++) {
    var ckv = curParts[j].split(':')
    var name = ckv[0]
    var phase = ckv[1]
    var was = before[name]
    if (was !== undefined && was !== phase && next[name] !== undefined) {
      delete next[name]
      changed = true
    }
  }
  return changed ? next : prevOverrides
}

// ═══════════════════════════════════════════════════════════════════════════════
// Lane layout helpers
// ═══════════════════════════════════════════════════════════════════════════════

var LANE_EXPANDED_WIDTH = 256
var LANE_COLLAPSED_WIDTH = 32

// ═══════════════════════════════════════════════════════════════════════════════
// Canonical status tone mapping — aligned with kanban/types.ts COLUMN_META
// ═══════════════════════════════════════════════════════════════════════════════

var STATUS_TONE = {
  'ideas': 'var(--ui-text-tertiary)',
  'draft': '#a78bfa',
  'todo': 'var(--ui-text-secondary)',
  'in-progress': '#34d399',
  'done': 'var(--ui-text-tertiary)',
  'archived': 'var(--ui-text-quaternary)',
}

function statusTone(status) {
  return STATUS_TONE[status] || 'var(--ui-text-secondary)'
}

function autoCollapseEmptyLanes(grouped, statusOrder) {
  var totalItems = 0
  for (var i = 0; i < statusOrder.length; i++) {
    var s = statusOrder[i]
    var items = grouped[s] || []
    totalItems += items.length
  }
  var collapsed = {}
  if (totalItems > 0) {
    for (var j = 0; j < statusOrder.length; j++) {
      var st = statusOrder[j]
      var col = grouped[st] || []
      if (col.length === 0) collapsed[st] = true
    }
  }
  return collapsed
}

function laneWidth(status, collapsedSet) {
  return (collapsedSet && collapsedSet[status]) ? LANE_COLLAPSED_WIDTH : LANE_EXPANDED_WIDTH
}

function railStyle() {
  return {
    width: LANE_COLLAPSED_WIDTH + 'px',
    minWidth: LANE_COLLAPSED_WIDTH + 'px',
    flexShrink: 0,
    height: '100%',
    cursor: 'pointer',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '4px',
    borderRadius: '8px',
    padding: '8px 0',
    overflow: 'hidden',
  }
}

function expandedStyle() {
  return {
    width: LANE_EXPANDED_WIDTH + 'px',
    minWidth: LANE_EXPANDED_WIDTH + 'px',
    flexShrink: 0,
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    background: 'color-mix(in srgb, var(--ui-bg-quinary) 50%, transparent)',
    borderRadius: '8px',
    padding: '8px',
    overflow: 'hidden',
  }
}

function parseTasks(content) {
  var total = 0, done = 0
  var sections = []
  var lines = (content || '').split('\n')
  var currentSection = null
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i]
    var headingMatch = line.match(/^#{1,6}\s+(.+)/)
    if (headingMatch) {
      currentSection = { title: headingMatch[1], done: 0, total: 0, tasks: [] }
      sections.push(currentSection)
    }
    var taskMatch = line.match(/^[-*]\s+\[([ xX])\]\s*(.*)/)
    if (taskMatch) {
      var isDone = taskMatch[1] === 'x' || taskMatch[1] === 'X'
      total++
      if (isDone) done++
      var task = { text: taskMatch[2], done: isDone }
      if (!currentSection) {
        currentSection = { title: 'Tasks', done: 0, total: 0, tasks: [] }
        sections.push(currentSection)
      }
      currentSection.total++
      if (isDone) currentSection.done++
      currentSection.tasks.push(task)
    }
  }
  return { total: total, done: done, sections: sections }
}

function renderMarkdown(content) {
  if (!content) return []
  var elements = []
  var lines = content.split('\n')
  var i = 0
  while (i < lines.length) {
    var line = lines[i]

    // Fenced code block
    if (line.match(/^```/)) {
      var lang = line.slice(3).trim()
      var codeLines = []
      i++
      while (i < lines.length && !lines[i].match(/^```/)) { codeLines.push(lines[i]); i++ }
      i++ // skip closing fence
      elements.push({ type: 'fenced', lang: lang, content: codeLines.join('\n') })
      continue
    }

    // Heading
    var headingMatch = line.match(/^(#{1,6})\s+(.*)/)
    if (headingMatch) {
      elements.push({ type: 'heading', level: headingMatch[1].length, text: headingMatch[2] })
      i++; continue
    }

    // Unordered list
    if (line.match(/^[-*]\s+/)) {
      elements.push({ type: 'list-item', ordered: false, text: line.replace(/^[-*]\s+/, '') })
      i++; continue
    }

    // Ordered list
    if (line.match(/^\d+\.\s+/)) {
      elements.push({ type: 'list-item', ordered: true, text: line.replace(/^\d+\.\s+/, '') })
      i++; continue
    }

    // Empty line
    if (line.trim() === '') { i++; continue }

    // Paragraph
    elements.push({ type: 'paragraph', text: line })
    i++
  }
  return elements
}

function classifyState(query) {
  if (query.isLoading) return 'loading'
  if (query.error) return 'error'
  if (query.data) {
    if (Array.isArray(query.data) && query.data.length === 0) return 'empty'
    if (query.data.sources && query.data.sources.length === 0) return 'empty'
    if (query.data.files && query.data.files.length === 0) return 'empty'
    if (query.data.items && Array.isArray(query.data.items) && query.data.items.length === 0) return 'empty'
    return 'content'
  }
  return 'empty'
}

function classifyDiffLine(line) {
  if (!line) return 'context'
  if (line.startsWith('+')) return 'added'
  if (line.startsWith('-')) return 'removed'
  if (line.startsWith('@@')) return 'hunk'
  return 'context'
}

function hasDiffMode(data, mode) {
  if (!data) return false
  if (mode === 'semantic') return !!(data.semantic_diff && (data.semantic_diff.groups || data.semantic_diff.requirements))
  if (mode === 'split') return !!(data.before != null && data.after != null)
  if (mode === 'raw') return !!(data.diff || data.raw_diff)
  return false
}

function effectiveDiffMode(desired, data) {
  if (hasDiffMode(data, desired)) return desired
  var fallback = ['semantic', 'split', 'raw']
  for (var i = 0; i < fallback.length; i++) {
    if (hasDiffMode(data, fallback[i])) return fallback[i]
  }
  return desired
}

function trimPath(raw) {
  return typeof raw === 'string' ? raw.trim() : ''
}

function extractApiError(err) {
  if (!err) return 'Unknown error'
  var candidate = typeof err === 'string' ? err : (err.message || err.detail)
  if (typeof candidate === 'string' && /\b409\b/.test(candidate) && candidate.indexOf('Source already registered') !== -1) {
    return 'Source already registered. Select it from the source list, or remove it before adding again.'
  }
  if (typeof err === 'string') return err
  if (err.message) return err.message
  if (err.detail) return err.detail
  return String(err)
}

function sourceNeedsInitialization(result) {
  var source = result && result.source
  return !!(source && source.id && source.valid === false && source.error === 'No openspec/ directory found')
}

function initializeAddedSource(api, result) {
  if (!sourceNeedsInitialization(result)) return Promise.resolve(result)
  return api.initSource(result.source.id).then(function(initResult) {
    return initResult && initResult.source && initResult.source.id ? initResult : result
  }).catch(function(e) {
    return Object.assign({}, result, { initError: extractApiError(e) })
  })
}

// ═══════════════════════════════════════════════════════════════════════════════
// API adapter — source registry mutations + read-only, namespace-scoped
// ═══════════════════════════════════════════════════════════════════════════════

function createApi(ctx) {
  return {
    sources: function() { return ctx.rest(sourcesPath()) },
    change: function(sourceId, name) { return ctx.rest(changePath(sourceId, name)) },
    idea: function(sourceId, name) { return ctx.rest(ideaPath(sourceId, name)) },
    specBrowser: function(sourceId, opts) { return ctx.rest(specBrowserPath(sourceId, opts)) },
    spec: function(sourceId, path) { return ctx.rest(specPath(sourceId, path)) },
    addSource: function(path, name) {
      return ctx.rest(sourcesPath(), { method: 'POST', body: { path: path, name: name || undefined } })
    },
    updateSource: function(sourceId, path, name) {
      return ctx.rest('/sources/' + encodeURIComponent(sourceId), { method: 'PUT', body: { path: path, name: name || undefined } })
    },
    initSource: function(sourceId) {
      return ctx.rest('/sources/' + encodeURIComponent(sourceId) + '/init', { method: 'POST' })
    },
    removeSource: function(sourceId) {
      return ctx.rest('/sources/' + encodeURIComponent(sourceId), { method: 'DELETE' })
    },
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Markdown renderer — safe subset, no innerHTML
// ═══════════════════════════════════════════════════════════════════════════════

function isSafeUrl(url) {
  if (!url) return false
  // Strip leading whitespace and control characters (U+0000-U+001F, U+007F-U+009F)
  var s = String(url).replace(/^[\s\x00-\x1f\x7f-\x9f]+/, '')
  if (!s) return false
  // Reject protocol-relative URLs
  if (s.startsWith('//')) return false
  // Allow relative paths and fragment-only links
  if (s.startsWith('/') || s.startsWith('#') || s.startsWith('?')) return true
  // Explicit scheme allowlist: http, https, mailto (case-insensitive)
  var lower = s.toLowerCase()
  if (lower.startsWith('http://') || lower.startsWith('https://') || lower.startsWith('mailto:')) return true
  // Everything else is rejected (javascript:, data:, file:, vbscript:, etc.)
  return false
}

function renderInline(text) {
  if (!text) return text
  var parts = []
  var remaining = text
  var regex = /(\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\))/g
  var lastIndex = 0
  var match
  while ((match = regex.exec(remaining)) !== null) {
    if (match.index > lastIndex) parts.push(remaining.slice(lastIndex, match.index))
    if (match[2]) parts.push(jsx('strong', { style: { fontWeight: 600 }, children: match[2] }))
    else if (match[3]) parts.push(jsx('code', { style: { background: 'var(--editor-background, #1e1e1e)', padding: '1px 4px', borderRadius: '3px', fontFamily: 'monospace', fontSize: '0.9em' }, children: match[3] }))
    else if (match[4]) {
      if (isSafeUrl(match[5])) {
        parts.push(jsx('a', { href: match[5], target: '_blank', rel: 'noopener noreferrer', style: { color: 'var(--link-foreground, #4fc3f7)', textDecoration: 'underline' }, children: match[4] }))
      } else {
        parts.push(jsx('span', { style: { color: 'var(--muted-foreground, #888)' }, children: match[4] + ' [unsafe link]' }))
      }
    }
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < remaining.length) parts.push(remaining.slice(lastIndex))
  return parts
}

function MarkdownElement(el) {
  if (typeof el === 'string') return el
  if (typeof el === 'number') return el
  if (!el || !el.type) return null
  switch (el.type) {
    case 'heading':
      return jsx('div', { style: { fontWeight: 'bold', fontSize: el.level <= 2 ? '1.1em' : '1em', margin: '8px 0 4px', color: 'var(--foreground, #e0e0e0)' }, children: renderInline(el.text) })
    case 'paragraph':
      return jsx('div', { style: { margin: '4px 0', color: 'var(--foreground, #e0e0e0)' }, children: renderInline(el.text) })
    case 'list-item':
      return jsxs('div', { style: { margin: '1px 0', paddingLeft: '16px', color: 'var(--foreground, #e0e0e0)' }, children: [
        el.ordered ? '  ' : '\u2022 ',
        renderInline(el.text)
      ] })
    case 'fenced':
      return jsx('pre', { style: { background: 'var(--editor-background, #1e1e1e)', padding: '8px', borderRadius: '4px', margin: '4px 0', overflow: 'auto', fontFamily: 'monospace', fontSize: '0.9em', color: 'var(--foreground, #e0e0e0)' }, children: el.content })
    default:
      return null
  }
}

function MarkdownView({ content }) {
  var elements = renderMarkdown(content)
  if (!elements || elements.length === 0) return jsx(EmptyState, { title: 'No content', description: 'This document is empty.' })
  return jsxs('div', { 'data-selectable-text': 'true', style: { padding: '12px' }, children: elements.map(function(el, i) { return jsx(MarkdownElement, Object.assign({}, el, { key: i })) }) })
}

// ═══════════════════════════════════════════════════════════════════════════════
// Query state wrapper
// ═══════════════════════════════════════════════════════════════════════════════

// Reusable retry error state: ErrorState with a Button child wired to onRetry.
// Real SDK ErrorStateProps has no onRetry — canonical pattern nests Button child.
function RetryErrorState({ title, description, onRetry }) {
  return jsx(ErrorState, {
    title: title,
    description: description,
    children: onRetry ? jsx(Button, {
      variant: 'outline',
      size: 'sm',
      onClick: onRetry,
      children: 'Retry'
    }) : null
  })
}

function QueryState({ query, onRetry, emptyTitle, emptyDescription, children }) {
  var state = classifyState(query)
  if (state === 'loading') return jsx(Loader, { type: 'lemniscate-bloom' })
  if (state === 'error') return jsx(RetryErrorState, {
    title: 'Request failed',
    description: (query.error && query.error.message) || 'Could not reach the backend.',
    onRetry: onRetry
  })
  if (state === 'empty') return jsx(EmptyState, { title: emptyTitle || 'Nothing found', description: emptyDescription || 'No data available.' })
  return children
}

// ═══════════════════════════════════════════════════════════════════════════════
// Source dialog — add/edit source registry entries
// ═══════════════════════════════════════════════════════════════════════════════

function SourceDialog({ mode, api, source, onClose, onSaved }) {
  var initialPath = source && source.path ? source.path : ''
  var initialName = source && source.name ? source.name : ''
  var _p = React.useState(initialPath)
  var _n = React.useState(initialName)
  var _busy = React.useState(false)
  var _err = React.useState('')
  var path = _p[0], setPath = _p[1]
  var name = _n[0], setName = _n[1]
  var busy = _busy[0], setBusy = _busy[1]
  var err = _err[0], setErr = _err[1]

  var title = mode === 'edit' ? 'Edit source' : 'Add source'

  function handleSave() {
    var trimmed = trimPath(path)
    if (!trimmed) { setErr('Path is required'); return }
    setBusy(true); setErr('')
    var promise = mode === 'edit' && source
      ? api.updateSource(source.id, trimmed, trimPath(name))
      : api.addSource(trimmed, trimPath(name))
    if (mode === 'add') {
      promise = promise.then(function(result) { return initializeAddedSource(api, result) })
    }
    promise.then(function(result) {
      setBusy(false)
      onSaved(result)
    }).catch(function(e) {
      setBusy(false)
      setErr(extractApiError(e))
    })
  }

  return jsx(Dialog, { open: true, onOpenChange: onClose, children: jsxs(DialogContent, { style: { padding: '16px', maxWidth: '480px' }, children: [
    jsx('h2', { style: { fontSize: '16px', fontWeight: 600, margin: '0 0 12px', color: 'var(--foreground, #e0e0e0)' }, children: title }),
    jsxs('div', { style: { display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }, children: [
      jsxs('div', { children: [
        jsx('label', { style: { fontSize: '12px', fontWeight: 500, color: 'var(--muted-foreground, #888)', marginBottom: '4px', display: 'block' }, children: 'Path *' }),
        jsx(Input, { value: path, onChange: function(e) { setPath(e.target.value) }, placeholder: '/path/to/repo', disabled: busy }),
      ] }),
      jsxs('div', { children: [
        jsx('label', { style: { fontSize: '12px', fontWeight: 500, color: 'var(--muted-foreground, #888)', marginBottom: '4px', display: 'block' }, children: 'Display name' }),
        jsx(Input, { value: name, onChange: function(e) { setName(e.target.value) }, placeholder: 'Optional display name', disabled: busy }),
      ] }),
    ] }),
    err ? jsx('div', { style: { padding: '8px 12px', background: 'var(--destructive-background, #3d1a1a)', borderRadius: '4px', fontSize: '12px', color: 'var(--destructive, #f44336)', marginBottom: '12px' }, children: err }) : null,
    jsxs('div', { style: { display: 'flex', justifyContent: 'flex-end', gap: '8px' }, children: [
      jsx(Button, { variant: 'outline', size: 'sm', onClick: onClose, disabled: busy, children: 'Cancel' }),
      jsx(Button, { size: 'sm', onClick: handleSave, disabled: busy, children: busy ? 'Saving...' : 'Save' }),
    ] }),
  ] }) })
}

// ═══════════════════════════════════════════════════════════════════════════════
// Card helpers
// ═══════════════════════════════════════════════════════════════════════════════

function CardTaskFraction({ item }) {
  var tasks = item.tasks || item.taskStats
  if (!tasks) return null
  var done = tasks.done != null ? tasks.done : (tasks.completed || 0)
  var total = tasks.total != null ? tasks.total : (tasks.count || 0)
  if (total === 0) return null
  return jsx(Badge, { variant: 'outline', children: '✅' + done + '/' + total })
}

function CardArtifacts({ item }) {
  var badges = []
  if (item.hasProposal) badges.push({ label: 'proposal', color: '#60a5fa' })
  if (item.hasTasks) badges.push({ label: 'tasks', color: '#34d399' })
  if (item.hasDesign) badges.push({ label: 'design', color: '#a78bfa' })
  if (item.hasSpecs) badges.push({ label: 'specs', color: '#fbbf24' })
  if (badges.length === 0) return null
  return jsxs('div', { style: { display: 'flex', gap: '4px', flexWrap: 'wrap' },
    children: badges.map(function(b, i) {
      return jsx(Badge, { variant: 'secondary', style: { fontSize: '10px', color: b.color }, children: b.label }, i)
    })
  })
}

function BoardCard({ item, source, allSources, allItems, onSelect }) {
  var token = item.token || item.name || ''
  var title = item.title || item.name || 'Untitled'
  var sequencePosition = normalizeSequencePosition(item.sequence)
  var itemRef = buildItemReference(source, item, allSources)
  var canCopy = !!itemRef && hasUniqueItemToken(item, allItems)
  var onClick = function() { onSelect(item) }
  var status = normalizeStatus(item.status || item.state || item.phase)
  return jsxs('div', {
    className: cn(
      'rounded-md border border-(--ui-stroke-tertiary) bg-(--ui-bg-elevated) px-3 pt-3 pb-0 cursor-pointer',
      'hover:border-(--ui-focus-border) hover:bg-primary/[0.06] hover:shadow-md transition-colors',
      'focus-visible:bg-(--ui-control-hover-background)'
    ),
    style: { borderLeftWidth: '2px', borderLeftColor: statusTone(status) },
    'data-selectable-text': 'true',
    tabIndex: 0,
    role: 'button',
    onClick: onClick,
    onKeyDown: function(e) { handleActivateKey(e, onClick) },
    children: [
      jsxs('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }, children: [
        jsx('div', { style: { fontWeight: 500, fontSize: '13px', color: 'var(--foreground, #e0e0e0)' }, children: title }),
        sequencePosition != null ? jsx(Badge, { variant: 'outline', style: { fontSize: '10px', flexShrink: 0 }, children: '#' + sequencePosition }) : null
      ] }),
      jsxs('div', { style: { display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '4px' }, children: [
        jsx(CardArtifacts, { item: item }),
        jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }, children: [
          jsx(CardTaskFraction, { item: item }),
          jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: '6px', marginLeft: 'auto', flexShrink: 0 }, children: [
            canCopy ? jsx(CopyButton, { appearance: 'icon', text: itemRef, label: 'Copy item reference', title: itemRef, stopPropagation: true }) : null,
            token ? jsx('span', { style: { fontFamily: 'monospace', fontSize: '10px', color: 'var(--muted-foreground, #888)' }, children: token }) : null,
          ] }),
        ] }),
      ] }),
    ]
  }, token || title)
}

// ═══════════════════════════════════════════════════════════════════════════════
// Board columns
// ═══════════════════════════════════════════════════════════════════════════════

var COLUMN_LABELS = {
  'ideas': 'Ideas',
  'draft': 'Draft',
  'todo': 'Todo',
  'in-progress': 'In Progress',
  'done': 'Done',
  'archived': 'Archived',
}

function BoardColumn({ status, items, source, allSources, allItems, onSelect, collapsed, onExpand }) {
  var label = COLUMN_LABELS[status] || status
  var sorted = sortItems(items)
  var count = items.length

  if (collapsed) {
    return jsx('div', {
      style: railStyle(),
      className: cn('focus-visible:bg-(--ui-control-hover-background) bg-[color-mix(in_srgb,var(--ui-bg-quinary)_50%,transparent)] hover:bg-(--ui-bg-quinary)'),
      tabIndex: 0,
      role: 'button',
      onClick: onExpand,
      onKeyDown: function(e) { handleActivateKey(e, onExpand) },
      title: label,
      'aria-label': label,
      children: [
        jsx('span', { style: { display: 'grid', height: '20px', placeItems: 'center', flexShrink: 0 }, children: [
          jsx('span', { style: { width: '6px', height: '6px', borderRadius: '50%', backgroundColor: statusTone(status) } }),
        ] }),
        jsx('span', { style: { fontSize: '11px', fontWeight: 600, color: 'var(--ui-text-tertiary)', letterSpacing: '0.05em', textTransform: 'uppercase', whiteSpace: 'nowrap', writingMode: 'vertical-rl' }, children: label }),
        count > 0 ? jsx('span', { style: { fontSize: '10px', color: 'var(--ui-text-quaternary)', fontVariantNumeric: 'tabular-nums' }, children: count }) : null,
      ]
    })
  }

  return jsxs('div', { style: expandedStyle(), 'data-lane': status, children: [
    jsxs('button', {
      type: 'button',
      onClick: onExpand,
      title: 'Collapse ' + label,
      'aria-label': 'Collapse ' + label,
      className: cn(
        'flex w-full items-center justify-between px-1 pb-2 bg-transparent border-0 text-inherit cursor-pointer text-left',
        'focus-visible:bg-(--ui-control-hover-background)'
      ),
      style: { fontSize: 'inherit' },
      onKeyDown: function(e) { handleActivateKey(e, onExpand) },
      children: [
        jsxs('span', { style: { display: 'flex', alignItems: 'center', gap: '6px' }, children: [
          jsx('span', { style: { width: '6px', height: '6px', borderRadius: '50%', backgroundColor: statusTone(status), flexShrink: 0 } }),
          jsx('span', { style: { fontWeight: 600, fontSize: '12px', textTransform: 'uppercase', color: 'var(--ui-text-tertiary)', letterSpacing: '0.05em' }, children: label }),
          count > 0 ? jsx('span', { style: { fontSize: '12px', color: 'var(--ui-text-quaternary)', fontVariantNumeric: 'tabular-nums' }, children: count }) : null,
        ] }),
        jsx('span', { style: { display: 'inline-flex', flexShrink: 0 }, children: jsx(Codicon, { name: 'chevron-left', size: '0.85rem' }) }),
      ]
    }),
    jsxs('div', { style: { flex: 1, overflowY: 'auto', overflowX: 'hidden', display: 'flex', flexDirection: 'column', gap: '8px', paddingRight: '4px' }, children: sorted.map(function(item) {
      return jsx(BoardCard, {
        item: item,
        source: source,
        allSources: allSources,
        allItems: allItems,
        onSelect: onSelect,
      }, item.token || item.name || item.title)
    }) }),
    items.length === 0 ? jsx('div', { style: { color: 'var(--muted-foreground, #666)', fontSize: '12px', padding: '12px 4px', fontStyle: 'italic' }, children: 'No items' }) : null,
  ] })
}

// ═══════════════════════════════════════════════════════════════════════════════
// Detail drawer
// ═══════════════════════════════════════════════════════════════════════════════

function DetailDrawer({ title, secondary, itemRef, canCopy, token, taskStats, onClose, children }) {
  return jsxs('div', {
    className: cn('absolute inset-y-0 right-0 z-20 flex w-[26rem] flex-col border-l border-(--ui-stroke-tertiary) bg-(--ui-bg-elevated) shadow-lg'),
    style: { minHeight: '0' },
    'data-detail-drawer': 'true',
    children: [
      jsxs('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid var(--ui-border, #333)', flexShrink: 0 }, children: [
        jsxs('div', { style: { minWidth: 0 }, children: [
          jsx('h2', { style: { fontSize: '16px', fontWeight: 600, margin: 0, color: 'var(--foreground, #e0e0e0)' }, children: title }),
          secondary ? jsx('div', { style: { fontSize: '12px', color: 'var(--muted-foreground, #888)', fontFamily: 'monospace', marginTop: '2px' }, children: secondary }) : null,
        ] }),
        jsx('button', {
          type: 'button',
          onClick: onClose,
          title: 'Close detail',
          'aria-label': 'Close detail',
          style: { background: 'none', border: 'none', color: 'var(--muted-foreground, #888)', cursor: 'pointer', padding: '4px', flexShrink: 0 },
          children: jsx(Codicon, { name: 'close', size: '1rem' })
        }),
      ] }),
      jsxs('div', { style: { display: 'flex', gap: '8px', alignItems: 'center', padding: '8px 16px', borderBottom: '1px solid var(--ui-border, #333)', flexShrink: 0 }, children: [
        canCopy ? jsx(CopyButton, { appearance: 'icon', text: itemRef, label: 'Copy item reference', title: itemRef }) : null,
        token ? jsx('span', { style: { fontSize: '12px', color: 'var(--muted-foreground, #888)', fontFamily: 'monospace' }, children: token }) : null,
        taskStats ? jsx(Badge, { variant: 'outline', children: taskStats.done + '/' + taskStats.total + ' tasks' }) : null,
      ] }),
      jsx('div', { 'data-selectable-text': 'true', style: { flex: 1, overflowY: 'auto', overflowX: 'hidden', minHeight: '0', padding: '8px 0' }, children: children }),
    ]
  })
}


// ═══════════════════════════════════════════════════════════════════════════════
// Change detail drawer
// ═══════════════════════════════════════════════════════════════════════════════

function ChangeDetailDrawer({ api, sourceId, change, source, allSources, allItems, onClose }) {
  var query = useQuery({
    queryKey: ['openspec', 'change', sourceId, change.name || change.token],
    queryFn: function() { return api.change(sourceId, change.name || change.token) }
  })

  var [activeTab, setActiveTab] = React.useState(null)

  var itemRef = buildItemReference(source, change, allSources)
  var canCopy = !!itemRef && hasUniqueItemToken(change, allItems)
  var title = query.data && query.data.title ? query.data.title : (change.title || change.name || 'Untitled change')
  var secondary = query.data && query.data.name ? query.data.name : (change.name || '')
  var token = change.token || change.name || ''

  if (query.isLoading) return jsx(DetailDrawer, { title: title, secondary: secondary, itemRef: itemRef, canCopy: canCopy, token: token, onClose: onClose, children: jsx(Loader, { type: 'lemniscate-bloom' }) })
  if (query.error) return jsx(DetailDrawer, { title: title, secondary: secondary, itemRef: itemRef, canCopy: canCopy, token: token, onClose: onClose, children: jsx(RetryErrorState, { title: 'Failed to load change', description: query.error.message, onRetry: function() { query.refetch() } }) })

  var data = query.data || {}
  var tabs = []
  if (data.proposal) tabs.push({ key: 'proposal', label: 'Proposal', content: jsx(MarkdownView, { content: stripFrontmatter(data.proposal) }) })
  if (data.tasks) tabs.push({ key: 'tasks', label: 'Tasks', content: jsx(TaskView, { content: stripFrontmatter(data.tasks) }) })
  if (data.design) tabs.push({ key: 'design', label: 'Design', content: jsx(MarkdownView, { content: stripFrontmatter(data.design) }) })
  if (data.specs && data.specs.length > 0) tabs.push({ key: 'specs', label: 'Specs', content: jsx(SpecsDetailView, { specs: data.specs }) })

  var currentTab = activeTab || (tabs.length > 0 ? tabs[0].key : null)

  // Use detailTitle/detailSecondaryName fallback helpers for consistency.
  title = detailTitle(data, change, change, 'change')
  secondary = detailSecondaryName(data, change)

  return jsx(DetailDrawer, {
    title: title,
    secondary: secondary,
    itemRef: itemRef,
    canCopy: canCopy,
    token: token,
    taskStats: data.taskStats,
    onClose: onClose,
    children: tabs.length > 0 ? jsxs(Tabs, { value: currentTab, onValueChange: setActiveTab, children: [
      jsx(TabsList, { children: tabs.map(function(t) { return jsx(TabsTrigger, { value: t.key, children: t.label }, t.key) }) }),
      tabs.map(function(t) { return currentTab === t.key ? jsx('div', { key: t.key, children: t.content }) : null }),
    ] }) : jsx(EmptyState, { title: 'No artifacts', description: 'This change has no proposal, tasks, design, or spec content.' })
  })
}

// ═══════════════════════════════════════════════════════════════════════════════
// Task view
// ═══════════════════════════════════════════════════════════════════════════════

function TaskView({ content }) {
  var parsed = parseTasks(content)
  return jsxs('div', { 'data-selectable-text': 'true', style: { padding: '12px' }, children: [
    jsxs('div', { style: { marginBottom: '12px', color: 'var(--muted-foreground, #888)', fontSize: '13px' }, children: [
      parsed.done + ' of ' + parsed.total + ' tasks completed',
    ] }),
    parsed.sections.map(function(section, i) {
      return jsxs('div', { style: { marginBottom: '12px' }, children: [
        jsx('div', { style: { fontWeight: 600, fontSize: '14px', marginBottom: '4px', color: 'var(--foreground, #e0e0e0)' }, children: section.title }),
        section.tasks.map(function(task, j) {
          return jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: '8px', padding: '2px 0', color: 'var(--foreground, #e0e0e0)' }, children: [
            jsx('span', { style: { color: task.done ? 'var(--primary, #4caf50)' : 'var(--muted-foreground, #888)' }, children: task.done ? '\u2611' : '\u2610' }),
            jsx('span', { style: { fontSize: '13px', textDecoration: task.done ? 'line-through' : 'none', opacity: task.done ? 0.6 : 1 }, children: task.text }),
          ] }, j)
        }),
      ] }, i)
    }),
    parsed.sections.length === 0 ? jsx(MarkdownView, { content: content }) : null,
  ] })
}

// ═══════════════════════════════════════════════════════════════════════════════
// Idea detail drawer
// ═══════════════════════════════════════════════════════════════════════════════

function IdeaDetailDrawer({ api, sourceId, idea, source, allSources, allItems, onClose }) {
  var query = useQuery({
    queryKey: ['openspec', 'idea', sourceId, idea.name || idea.token],
    queryFn: function() { return api.idea(sourceId, idea.name || idea.token) }
  })

  var itemRef = buildItemReference(source, idea, allSources)
  var canCopy = !!itemRef && hasUniqueItemToken(idea, allItems)
  var title = query.data && query.data.title ? query.data.title : (idea.title || idea.name || 'Untitled idea')
  var secondary = ideaSecondaryName(query.data && query.data.name ? query.data.name : (idea.name || ''))
  var token = idea.token || idea.name || ''

  if (query.isLoading) return jsx(DetailDrawer, { title: title, secondary: secondary, itemRef: itemRef, canCopy: canCopy, token: token, onClose: onClose, children: jsx(Loader, { type: 'lemniscate-bloom' }) })
  if (query.error) return jsx(DetailDrawer, { title: title, secondary: secondary, itemRef: itemRef, canCopy: canCopy, token: token, onClose: onClose, children: jsx(RetryErrorState, { title: 'Failed to load idea', description: query.error.message, onRetry: function() { query.refetch() } }) })

  var data = query.data || {}

  // Reconcile title/secondary with canonical fallback helpers.
  title = detailTitle(data, idea, idea, 'idea')
  secondary = ideaSecondaryName(detailSecondaryName(data, idea))

  // Strip YAML frontmatter from content before rendering
  var content = data.content || ''
  var stripped = stripFrontmatter(content)

  return jsx(DetailDrawer, { title: title, secondary: secondary, itemRef: itemRef, canCopy: canCopy, token: token, onClose: onClose, children: jsx(MarkdownView, { content: stripped }) })
}

// ═══════════════════════════════════════════════════════════════════════════════
// Change spec detail — Proposed and Diff views
// ═══════════════════════════════════════════════════════════════════════════════

function DiffModePanel({ data }) {
  var [diffMode, setDiffMode] = React.useState('semantic')
  var effMode = effectiveDiffMode(diffMode, data)
  return jsxs('div', { children: [
    hasDiffMode(data, 'semantic') || hasDiffMode(data, 'split') || hasDiffMode(data, 'raw') ? jsxs('div', { style: { display: 'flex', gap: '4px', marginBottom: '8px' }, children: [
      hasDiffMode(data, 'semantic') ? jsx(Button, { variant: effMode === 'semantic' ? 'default' : 'outline', size: 'sm', onClick: function() { setDiffMode('semantic') }, children: 'Semantic' }) : null,
      hasDiffMode(data, 'split') ? jsx(Button, { variant: effMode === 'split' ? 'default' : 'outline', size: 'sm', onClick: function() { setDiffMode('split') }, children: 'Side-by-side' }) : null,
      hasDiffMode(data, 'raw') ? jsx(Button, { variant: effMode === 'raw' ? 'default' : 'outline', size: 'sm', onClick: function() { setDiffMode('raw') }, children: 'Raw' }) : null,
    ] }) : null,
    effMode === 'semantic' && hasDiffMode(data, 'semantic') ? jsx(SemanticDiffView, { data: data.semantic_diff }) : null,
    effMode === 'split' && hasDiffMode(data, 'split') ? jsx(SplitDiffView, { before: data.before, after: data.after }) : null,
    effMode === 'raw' && hasDiffMode(data, 'raw') ? jsx(RawDiffView, { diff: data.diff || data.raw_diff }) : null,
  ] })
}

function SpecsDetailView({ specs }) {
  var [selectedIdx, setSelectedIdx] = React.useState(0)

  if (!specs || specs.length === 0) return jsx(EmptyState, { title: 'No specs', description: 'No spec changes in this change.' })
  var spec = specs[selectedIdx] || specs[0]

  return jsxs('div', { 'data-selectable-text': 'true', style: { padding: '12px' }, children: [
    specs.length > 1 ? jsxs('div', { style: { marginBottom: '8px' }, children: [
      jsx('select', {
        value: selectedIdx,
        onChange: function(e) { setSelectedIdx(parseInt(e.target.value, 10)) },
        style: { padding: '4px 8px', borderRadius: '4px', border: '1px solid var(--ui-border, #333)', background: 'var(--input-background, #2a2a2a)', color: 'var(--foreground, #e0e0e0)' },
        children: specs.map(function(s, i) { return jsx('option', { value: i, children: s.path || s.title || ('Spec ' + (i + 1)) }, i) })
      })
    ] }) : null,
    spec.path ? jsx('div', { style: { fontSize: '12px', color: 'var(--muted-foreground, #888)', marginBottom: '8px', fontFamily: 'monospace' }, children: spec.path }) : null,
    spec.status ? jsx(Badge, { variant: 'outline', style: { marginBottom: '8px' }, children: spec.status }) : null,
    jsx(DiffModePanel, { data: spec }),
    spec.content ? jsx(MarkdownView, { content: stripFrontmatter(spec.content) }) : null,
  ] })
}

// ═══════════════════════════════════════════════════════════════════════════════
// Diff views
// ═══════════════════════════════════════════════════════════════════════════════

function normalizeSemanticGroups(data) {
  if (!data) return []
  // Legacy flat groups array (data.groups)
  if (data.groups && Array.isArray(data.groups)) return data.groups
  // Backend contract: {status, requirements: {added, modified, removed, unchanged}}
  var reqs = data.requirements
  if (!reqs || typeof reqs !== 'object' || Array.isArray(reqs)) return []
  var items = []
  var added = reqs.added || []
  var modified = reqs.modified || []
  var removed = reqs.removed || []
  for (var i = 0; i < added.length; i++) {
    var a = added[i]
    items.push({ label: 'Added', name: a.name || '', description: a.description || '', color: 'var(--primary, #4caf50)' })
  }
  for (var j = 0; j < modified.length; j++) {
    var m = modified[j]
    var beforeDesc = m.before && typeof m.before === 'object' ? (m.before.description || '') : String(m.before || '')
    var afterDesc = m.after && typeof m.after === 'object' ? (m.after.description || '') : String(m.after || '')
    items.push({ label: 'Modified', name: m.name || '', description: '', before: beforeDesc, after: afterDesc, color: 'var(--warning, #ff9800)' })
  }
  for (var k = 0; k < removed.length; k++) {
    var r = removed[k]
    items.push({ label: 'Removed', name: r.name || '', description: r.description || '', color: 'var(--destructive, #f44336)' })
  }
  return items
}

function SemanticDiffView({ data }) {
  if (!data) return null
  var items = normalizeSemanticGroups(data)
  return jsxs('div', { style: { padding: '8px' }, children: [
    jsx('div', { style: { fontWeight: 600, marginBottom: '8px', color: 'var(--foreground, #e0e0e0)' }, children: 'Semantic Changes' }),
    items.map(function(item, i) {
      return jsxs('div', { style: { marginBottom: '8px', padding: '8px', background: 'var(--card-background, #1a1a1a)', borderRadius: '4px', border: '1px solid var(--ui-border, #333)' }, children: [
        jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }, children: [
          jsx('span', { style: { fontSize: '10px', fontWeight: 600, padding: '1px 5px', borderRadius: '3px', background: item.color, color: '#fff' }, children: item.label }),
          item.name ? jsx('span', { style: { fontWeight: 500, color: 'var(--foreground, #e0e0e0)' }, children: item.name }) : null,
        ] }),
        item.description ? jsx('div', { style: { fontSize: '12px', color: 'var(--muted-foreground, #888)', marginBottom: '2px' }, children: item.description }) : null,
        item.before != null && item.before !== '' ? jsx('div', { style: { color: 'var(--destructive, #f44336)', fontSize: '12px', marginBottom: '2px' }, children: '- ' + item.before }) : null,
        item.after != null && item.after !== '' ? jsx('div', { style: { color: 'var(--primary, #4caf50)', fontSize: '12px' }, children: '+ ' + item.after }) : null,
      ] }, i)
    }),
  ] })
}

function SplitDiffView({ before, after }) {
  return jsxs('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', padding: '8px' }, children: [
    jsxs('div', { children: [
      jsx('div', { style: { fontWeight: 500, marginBottom: '4px', color: 'var(--muted-foreground, #888)', fontSize: '12px' }, children: 'Before' }),
      jsx('pre', { style: { fontSize: '12px', fontFamily: 'monospace', whiteSpace: 'pre-wrap', padding: '8px', background: 'var(--editor-background, #1e1e1e)', borderRadius: '4px', color: 'var(--foreground, #e0e0e0)', margin: 0 }, children: before || '' }),
    ] }),
    jsxs('div', { children: [
      jsx('div', { style: { fontWeight: 500, marginBottom: '4px', color: 'var(--muted-foreground, #888)', fontSize: '12px' }, children: 'After' }),
      jsx('pre', { style: { fontSize: '12px', fontFamily: 'monospace', whiteSpace: 'pre-wrap', padding: '8px', background: 'var(--editor-background, #1e1e1e)', borderRadius: '4px', color: 'var(--foreground, #e0e0e0)', margin: 0 }, children: after || '' }),
    ] }),
  ] })
}

function RawDiffView({ diff }) {
  if (!diff) return null
  var lines = Array.isArray(diff) ? diff : String(diff).split('\n')
  return jsxs('pre', { style: { fontSize: '12px', fontFamily: 'monospace', whiteSpace: 'pre-wrap', padding: '8px', background: 'var(--editor-background, #1e1e1e)', borderRadius: '4px', margin: 0 }, children: lines.map(function(line, i) {
    var cls = classifyDiffLine(line)
    var style = { display: 'block', padding: '1px 4px' }
    if (cls === 'added') style.color = 'var(--primary, #4caf50)'
    else if (cls === 'removed') style.color = 'var(--destructive, #f44336)'
    else if (cls === 'hunk') style.color = 'var(--muted-foreground, #888)'
    else style.color = 'var(--foreground, #e0e0e0)'
    return jsx('span', { style: style, children: line + '\n' }, i)
  }) })
}

// ═══════════════════════════════════════════════════════════════════════════════
// Work view
// ═══════════════════════════════════════════════════════════════════════════════

function WorkView({ api, source, sources, onSelectItem, showArchived, onToggleArchived }) {
  var ideas = (source.openspec && source.openspec.ideas) || []
  var changes = (source.openspec && source.openspec.changes) || []
  var allItems = ideas.map(function(idea) {
    return Object.assign({}, idea, { _type: 'idea' })
  }).concat(changes.map(function(change) {
    return Object.assign({}, change, { _type: 'change' })
  }))

  var [filter, setFilter] = React.useState('')
  var [manualOverrides, setManualOverrides] = React.useState({})
  var prevLanePhase = React.useRef(null)

  var filtered = filterItems(allItems, filter)
  var visibleStatuses = showArchived ? STATUS_ORDER : STATUS_ORDER.filter(function(s) { return s !== 'archived' })
  var grouped = groupByStatus(filtered, showArchived)
  var autoCollapsed = autoCollapseEmptyLanes(grouped, visibleStatuses)

  // Lane phase tracking — prune overrides when empty/full flips
  var lanePhase = computeLanePhase(grouped, visibleStatuses)
  React.useEffect(function() {
    if (lanePhase === null || lanePhase === prevLanePhase.current) return
    var prev = prevLanePhase.current
    prevLanePhase.current = lanePhase
    if (prev === null) return
    setManualOverrides(function(prevOverrides) {
      return pruneStaleOverrides(prevOverrides, prev, lanePhase)
    })
  }, [lanePhase])

  var collapsedSet = computeCollapsedSet(autoCollapsed, manualOverrides, visibleStatuses)

  function toggleCollapse(status) {
    setManualOverrides(function(prev) {
      return toggleOverride(prev, status, autoCollapsed)
    })
  }

  return jsxs('div', { style: { display: 'flex', flexDirection: 'column', gap: '8px', height: '100%', overflow: 'hidden', minWidth: 0, minHeight: 0 }, children: [
    jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: '6px', padding: '0 4px', flexShrink: 0 }, children: [
      jsx('span', { style: { display: 'inline-flex', alignItems: 'center', color: 'var(--muted-foreground, #888)', lineHeight: 1 }, title: 'Filter', 'aria-label': 'Filter', children: jsx(Codicon, { name: 'filter', size: '0.85rem' }) }),
      jsx(Input, { placeholder: 'title, token, or name...', value: filter, onChange: function(e) { setFilter(e.target.value) }, style: { flex: 1 } }),
      jsx(Button, { variant: 'outline', size: 'sm', type: 'button', 'aria-pressed': showArchived, style: { backgroundColor: showArchived ? 'var(--ui-control-active-background)' : undefined }, onClick: function() { onToggleArchived(!showArchived) }, children: [showArchived ? '\u2713' : null, ' ', 'Archived'] }),
    ] }),
    jsx('div', { style: { display: 'flex', gap: '8px', flex: 1, overflowX: 'auto', overflowY: 'hidden', minWidth: 0, minHeight: 0, paddingBottom: '8px' }, children: visibleStatuses.map(function(status) {
      var items = grouped[status] || []
      return jsx(BoardColumn, {
        status: status,
        items: items,
        source: source,
        allSources: sources,
        allItems: allItems,
        onSelect: onSelectItem,
        collapsed: !!collapsedSet[status],
        onExpand: function() { toggleCollapse(status) },
      }, status)
    }) }),
  ] })
}

// ═══════════════════════════════════════════════════════════════════════════════
// Specs view
// ═══════════════════════════════════════════════════════════════════════════════

function SpecsView({ api, sourceId }) {
  var [worktree, setWorktree] = React.useState(false)

  var query = useQuery({
    queryKey: ['openspec', 'spec-browser', sourceId, worktree],
    queryFn: function() { return api.specBrowser(sourceId, { dirty: worktree }) },
  })

  var [selectedFile, setSelectedFile] = React.useState(null)

  // Reset selected file when source changes — component remounts via key prop
  React.useEffect(function() {
    setSelectedFile(null)
  }, [sourceId])

  // Gate spec query on file selection
  var specQuery = useQuery({
    queryKey: ['openspec', 'spec', sourceId, selectedFile],
    queryFn: function() { return api.spec(sourceId, selectedFile) },
    enabled: !!selectedFile && !worktree,
  })

  var files = (query.data && query.data.files) || []
  var branch = query.data && query.data.branch
  var changedCount = query.data && query.data.changedCount != null ? query.data.changedCount : files.length

  return jsxs('div', { style: { display: 'flex', flexDirection: 'column', gap: '12px', height: '100%' }, children: [
    jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: '8px', padding: '0 4px' }, children: [
      jsx(Button, { variant: worktree ? 'outline' : 'default', size: 'sm', onClick: function() { setWorktree(false); setSelectedFile(null) }, children: 'Current' }),
      jsx(Button, { variant: worktree ? 'default' : 'outline', size: 'sm', onClick: function() { setWorktree(true); setSelectedFile(null) }, children: 'Worktree' }),
      branch ? jsx('span', { style: { fontSize: '12px', color: 'var(--muted-foreground, #888)' }, children: branch }) : null,
      worktree ? jsx(Badge, { variant: 'outline', children: changedCount + ' changed' }) : null,
    ] }),
    query.isLoading ? jsx(Loader, { type: 'lemniscate-bloom' }) : null,
    query.error ? jsx(RetryErrorState, { title: 'Failed to load specs', description: query.error.message, onRetry: function() { query.refetch() } }) : null,
    !query.isLoading && !query.error && files.length === 0 ? jsx(EmptyState, {
      title: worktree ? 'No spec changes between HEAD and worktree' : 'No specs found',
      description: worktree ? 'The working tree matches HEAD for all spec files.' : 'No spec files are registered for this source.',
    }) : null,
    !query.isLoading && files.length > 0 ? jsxs('div', { style: { display: 'flex', gap: '12px', flex: 1, overflow: 'hidden' }, children: [
      jsxs('div', { style: { width: '240px', flexShrink: 0, overflow: 'auto' }, children: [
        files.map(function(file) {
          var path = file.path || file.name || file
          var isSelected = selectedFile === path
          return jsxs('div', {
            className: cn(
              'px-3 py-2 cursor-pointer text-sm rounded-md',
              isSelected ? 'bg-(--ui-selected-background, #2a2a2a) text-foreground' : 'text-muted-foreground hover:bg-(--ui-hover-background, #1a1a1a)'
            ),
            onClick: function() { setSelectedFile(path) },
            children: [
              jsx('div', { style: { fontFamily: 'monospace', fontSize: '12px' }, children: path }),
              file.status ? jsx(Badge, { variant: 'outline', style: { fontSize: '10px', marginTop: '2px' }, children: file.status }) : null,
            ]
          }, path)
        }),
      ] }),
      jsxs('div', { style: { flex: 1, overflow: 'auto' }, children: [
        worktree && selectedFile ? jsx(WorktreeDetailView, { sourceId: sourceId, file: selectedFile, files: files }) : null,
        !worktree && selectedFile && specQuery.isLoading ? jsx(Loader, { type: 'lemniscate-bloom' }) : null,
        !worktree && selectedFile && specQuery.error ? jsx(RetryErrorState, { title: 'Failed to load spec', description: specQuery.error.message, onRetry: function() { specQuery.refetch() } }) : null,
        !worktree && selectedFile && !specQuery.isLoading && !specQuery.error ? jsx(MarkdownView, { content: stripFrontmatter(specQuery.data && specQuery.data.content) }) : null,
        !selectedFile ? jsx(EmptyState, { title: 'Select a file', description: 'Choose a spec file from the list to view its content.' }) : null,
      ] }),
    ] }) : null,
  ] })
}

function WorktreeDetailView({ sourceId, file, files }) {
  var fileInfo = files.find(function(f) { return (f.path || f.name || f) === file }) || {}

  var data = fileInfo

  return jsxs('div', { style: { padding: '12px' }, children: [
    jsxs('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }, children: [
      jsx('h3', { style: { fontSize: '14px', fontWeight: 500, margin: 0, color: 'var(--foreground, #e0e0e0)' }, children: file }),
      fileInfo.status ? jsx(Badge, { variant: 'outline', children: fileInfo.status }) : null,
    ] }),
    jsx(DiffModePanel, { data: data }),
    !hasDiffMode(data, 'semantic') && !hasDiffMode(data, 'split') && !hasDiffMode(data, 'raw') && data.content ? jsx(MarkdownView, { content: stripFrontmatter(data.content) }) : null,
    !hasDiffMode(data, 'semantic') && !hasDiffMode(data, 'split') && !hasDiffMode(data, 'raw') && !data.content ? jsx(EmptyState, { title: 'No diff data', description: 'No diff representation available for this file.' }) : null,
  ] })
}

// ═══════════════════════════════════════════════════════════════════════════════
// Main page
// ═══════════════════════════════════════════════════════════════════════════════

function OpenSpecPage({ api, sessionStore }) {
  var sourcesQuery = useQuery({
    queryKey: ['openspec', 'sources'],
    queryFn: function() { return api.sources() },
  })

  var [selectedSourceId, setSelectedSourceId] = React.useState(sessionStore ? sessionStore.selectedSourceId : null)
  var [view, setView] = React.useState('work')
  var [showArchived, setShowArchived] = React.useState(sessionStore ? sessionStore.showArchived : true)
  var [selectedItem, setSelectedItem] = React.useState(null) // {item, sourceId, type}
  var [sourceDialog, setSourceDialog] = React.useState(null) // {mode: 'add'|'edit'} or null
  var [removeConfirm, setRemoveConfirm] = React.useState(null) // source object or null
  var [removeBusy, setRemoveBusy] = React.useState(false)
  var [removeError, setRemoveError] = React.useState('')
  var [initBusy, setInitBusy] = React.useState(false)
  var [initError, setInitError] = React.useState('')

  // Resolve selection after refreshed /sources data: restore the retained source
  // while its ID remains present (including invalid sources), otherwise fall back
  // to first-valid / first-returned; update the registration-scope store both ways.
  // The effect is gated on data arrival: during the loading window
  // sourcesQuery.data is still undefined, and resolving against the pre-data
  // empty list would wipe a retained selection (both React state and the
  // registration-scope store) before refreshed /sources data ever arrives. The
  // retained ID survives the loading render, so resolution — and the null rule
  // for genuinely empty results — only ever runs against the refreshed list.
  var sources = (sourcesQuery.data && sourcesQuery.data.sources) || []
  var previousResolvedInvalid = React.useRef(false)
  React.useEffect(function() {
    if (sourcesQuery.data === undefined) return
    var next = resolveRetainedSource(sources, selectedSourceId)
    var resolved = sources.find(function(s) { return s.id === next }) || null
    var resolvedInvalid = resolved && resolved.valid === false
    if (next === selectedSourceId) {
      if (resolvedInvalid && !previousResolvedInvalid.current) {
        setSelectedItem(null)
      }
      previousResolvedInvalid.current = !!resolvedInvalid
      if (sessionStore && next !== null) sessionStore.selectedSourceId = next
      return
    }
    setSelectedSourceId(next)
    setSelectedItem(null)
    previousResolvedInvalid.current = !!resolvedInvalid
    if (sessionStore) sessionStore.selectedSourceId = next
  }, [sources, sourcesQuery.data, selectedSourceId])

  // Close detail on explicit source change by user
  React.useEffect(function() {
    setSelectedItem(null)
  }, [selectedSourceId])

  var selectedSource = sources.find(function(s) { return s.id === selectedSourceId }) || null
  var sourceRef = buildSourceReference(selectedSource, sources)
  var allItems = []
  if (selectedSource && selectedSource.openspec) {
    var loadedIdeas = selectedSource.openspec.ideas || []
    var loadedChanges = selectedSource.openspec.changes || []
    allItems = loadedIdeas.map(function(idea) {
      return Object.assign({}, idea, { _type: 'idea' })
    }).concat(loadedChanges.map(function(change) {
      return Object.assign({}, change, { _type: 'change' })
    }))
  }

  function handleSelectSource(v) {
    setSelectedSourceId(v)
    if (sessionStore) sessionStore.selectedSourceId = v
  }
  function handleToggleArchived(v) {
    setShowArchived(v)
    if (sessionStore) sessionStore.showArchived = v
  }

  if (sourcesQuery.isLoading) return jsx(Loader, { type: 'lemniscate-bloom' })
  if (sourcesQuery.error) return jsx(RetryErrorState, { title: 'Failed to load sources', description: sourcesQuery.error.message, onRetry: function() { sourcesQuery.refetch() } })

  var onSelectItem = function(item) {
    setSelectedItem({ item: item, sourceId: selectedSourceId, type: item._type || 'change' })
  }

  function handleAddSource() { setSourceDialog({ mode: 'add' }) }
  function handleEditSource() { if (selectedSource) setSourceDialog({ mode: 'edit' }) }
  function handleInitSource() {
    if (!selectedSource || initBusy) return
    setInitBusy(true); setInitError('')
    api.initSource(selectedSource.id).then(function() {
      setInitBusy(false)
      sourcesQuery.refetch()
    }).catch(function(e) {
      setInitBusy(false)
      setInitError(extractApiError(e))
    })
  }
  function handleRemoveSource() {
    if (!selectedSource) return
    setRemoveConfirm(selectedSource)
    setRemoveError('')
  }
  function confirmRemove() {
    if (!removeConfirm) return
    setRemoveBusy(true); setRemoveError('')
    api.removeSource(removeConfirm.id).then(function() {
      setRemoveBusy(false); setRemoveConfirm(null)
      setSelectedSourceId(null)
      sourcesQuery.refetch()
    }).catch(function(e) {
      setRemoveBusy(false)
      setRemoveError(extractApiError(e))
    })
  }
  function onSourceSaved(result) {
    setSourceDialog(null)
    setInitError(result && result.initError ? result.initError : '')
    var refresh = sourcesQuery.refetch()
    if (result && result.source && result.source.id) {
      var selectReturnedSource = function() {
        setSelectedSourceId(result.source.id)
        if (sessionStore) sessionStore.selectedSourceId = result.source.id
      }
      if (refresh && typeof refresh.then === 'function') {
        refresh.then(selectReturnedSource, selectReturnedSource)
      } else {
        selectReturnedSource()
      }
    }
  }

  return jsxs('div', { className: cn('relative flex flex-col h-full overflow-hidden'), children: [
    jsx('style', { children: SOURCE_TRIGGER_HOVER_CSS }),

    // Header
    jsxs('div', { style: { padding: '6px 16px', borderBottom: '1px solid var(--ui-border, #333)', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'nowrap' }, children: [
      jsx('h1', { style: { fontSize: '13px', fontWeight: 600, margin: 0, color: 'var(--foreground, #e0e0e0)' }, children: 'OpenSpec' }),
      selectedSource && selectedSource.path ? jsx('span', { style: { minWidth: 0, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'monospace', fontSize: '11px', color: 'var(--muted-foreground, #888)' }, title: selectedSource.path, children: selectedSource.path }) : null,
    ] }),

    // Source controls and path line
    jsxs('div', { style: { padding: '6px 16px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--muted-foreground, #888)', borderBottom: '1px solid var(--ui-border, #333)' }, children: [
      selectedSource ? jsx(CopyButton, { appearance: 'icon', text: sourceRef, label: 'Copy source reference', title: sourceRef, disabled: !sourceRef }) : null,
      jsx(Select, {
        value: selectedSourceId || undefined,
        onValueChange: handleSelectSource,
        children: [
          jsx(SelectTrigger, { className: 'bg-(--ui-bg-quinary) transition-colors hover:bg-primary/[0.06] hover:bg-primary/[0.06]!', 'data-openspec-source-trigger': 'true', style: { minWidth: '120px', flexShrink: 1 }, children: jsx(SelectValue, { placeholder: 'Select source' }) }),
          jsx(SelectContent, { children: sources.map(function(s) {
            return jsx(SelectItem, { value: s.id, children: (s.name || s.id) + (s.valid === false ? ' (invalid)' : '') }, s.id)
          }) })
        ]
      }),
      jsx(Button, { variant: 'outline', size: 'sm', style: { padding: '4px', minWidth: 'auto', flexShrink: 0 }, title: 'Refresh sources', 'aria-label': 'Refresh sources', onClick: function() { sourcesQuery.refetch() }, children: jsx(Codicon, { name: 'refresh', size: '0.85rem' }) }),
      jsx(Button, { variant: 'ghost', size: 'sm', style: { padding: '2px 6px', fontSize: '11px', minWidth: 'auto', flexShrink: 0, whiteSpace: 'nowrap' }, title: 'Add source', 'aria-label': 'Add source', onClick: handleAddSource, children: ['+', ' Add'] }),
      selectedSource ? jsx(Button, { variant: 'ghost', size: 'sm', style: { padding: '2px 6px', fontSize: '11px', minWidth: 'auto', flexShrink: 0, whiteSpace: 'nowrap' }, title: 'Edit source', 'aria-label': 'Edit source', onClick: handleEditSource, children: ['\u270E', ' Edit'] }) : null,
      selectedSource ? jsx(Button, { variant: 'ghost', size: 'sm', style: { padding: '2px 6px', fontSize: '11px', minWidth: 'auto', flexShrink: 0, whiteSpace: 'nowrap' }, title: 'Delete source', 'aria-label': 'Delete source', onClick: handleRemoveSource, children: ['\u2715', ' Delete'] }) : null,
    ] }),

    // View switch
    jsxs('div', { style: { padding: '8px 16px', borderBottom: '1px solid var(--ui-border, #333)', display: 'flex', alignItems: 'center', gap: '12px' }, children: [
      jsx(SegmentedControl, {
        value: view,
        onChange: setView,
        options: [
          { id: 'work', label: 'Work' },
          { id: 'specs', label: 'Specs' },
        ]
      }),
      selectedSource && selectedSource.openspec && selectedSource.openspec.counts ? jsxs('div', { style: { display: 'flex', gap: '4px', fontSize: '10px', color: 'var(--muted-foreground, #888)' }, children: [
        selectedSource.openspec.counts.changes != null ? jsx(Badge, { variant: 'outline', children: selectedSource.openspec.counts.changes + ' changes' }) : null,
        selectedSource.openspec.counts.ideas != null ? jsx(Badge, { variant: 'outline', children: selectedSource.openspec.counts.ideas + ' ideas' }) : null,
        selectedSource.openspec.counts.specs != null ? jsx(Badge, { variant: 'outline', children: selectedSource.openspec.counts.specs + ' specs' }) : null,
      ] }) : null,
    ] }),

    // Invalid source warning
    selectedSource && selectedSource.valid === false ? jsx('div', { style: { padding: '12px 16px', background: 'var(--warning-background, #fff3cd)', borderRadius: '4px', margin: '8px 16px', fontSize: '13px' }, children: jsxs('div', { children: [
      jsxs('div', { children: [
        jsx('strong', { children: 'Invalid source' }),
        selectedSource.error ? ': ' + selectedSource.error : '',
        selectedSource.path ? jsxs('div', { style: { fontFamily: 'monospace', fontSize: '11px', marginTop: '4px', opacity: 0.7 }, children: ['Path: ', selectedSource.path] }) : null,
      ] }),
      selectedSource.error === 'No openspec/ directory found' ? jsx(Button, { size: 'sm', onClick: handleInitSource, disabled: initBusy, style: { marginTop: '10px' }, children: initBusy ? 'Initializing...' : 'Initialize OpenSpec' }) : null,
      initError ? jsx('div', { style: { marginTop: '8px', color: 'var(--destructive, #f44336)', fontSize: '12px' }, children: initError }) : null,
    ] }) }) : null,

    // View body
    jsx('div', { style: { flex: 1, overflow: 'hidden', padding: '12px 16px' }, children: selectedSource && selectedSource.valid !== false ? (
      view === 'work'
        ? jsx(WorkView, { key: selectedSource.id, api: api, source: selectedSource, sources: sources, showArchived: showArchived, onToggleArchived: handleToggleArchived, onSelectItem: onSelectItem })
        : jsx(SpecsView, { key: selectedSource.id, api: api, sourceId: selectedSource.id })
    ) : selectedSource && selectedSource.valid === false ? null : jsx(EmptyState, {
      title: sources.length === 0 ? 'No sources registered' : 'Select a source',
      description: sources.length === 0 ? 'Add a source to get started.' : 'Choose a source to view its OpenSpec project.'
    }) }),

    // Detail drawer — synchronous gate: reject stale item from different source
    selectedItem && selectedItem.sourceId === selectedSourceId && selectedItem.type === 'change' && selectedSource && selectedSource.valid !== false ? jsx(ChangeDetailDrawer, { api: api, sourceId: selectedSourceId, change: selectedItem.item, source: selectedSource, allSources: sources, allItems: allItems, onClose: function() { setSelectedItem(null) } }) : null,
    selectedItem && selectedItem.sourceId === selectedSourceId && selectedItem.type === 'idea' && selectedSource && selectedSource.valid !== false ? jsx(IdeaDetailDrawer, { api: api, sourceId: selectedSourceId, idea: selectedItem.item, source: selectedSource, allSources: sources, allItems: allItems, onClose: function() { setSelectedItem(null) } }) : null,

    // Source add/edit dialog
    sourceDialog ? jsx(SourceDialog, { mode: sourceDialog.mode, api: api, source: sourceDialog.mode === 'edit' ? selectedSource : null, onClose: function() { setSourceDialog(null) }, onSaved: onSourceSaved }) : null,

    // Remove source confirmation dialog
    removeConfirm ? jsx(Dialog, { open: true, onOpenChange: function() { if (!removeBusy) { setRemoveConfirm(null); setRemoveError('') } }, children: jsxs(DialogContent, { style: { padding: '16px', maxWidth: '400px' }, children: [
      jsx('h2', { style: { fontSize: '16px', fontWeight: 600, margin: '0 0 8px', color: 'var(--foreground, #e0e0e0)' }, children: 'Remove source' }),
      jsx('p', { style: { fontSize: '13px', color: 'var(--muted-foreground, #888)', margin: '0 0 12px' }, children: 'Remove source "' + (removeConfirm.name || removeConfirm.id) + '"? This unregisters the source from OpenSpec but does not delete any files.' }),
      removeError ? jsx('div', { style: { padding: '8px 12px', background: 'var(--destructive-background, #3d1a1a)', borderRadius: '4px', fontSize: '12px', color: 'var(--destructive, #f44336)', marginBottom: '12px' }, children: removeError }) : null,
      jsxs('div', { style: { display: 'flex', justifyContent: 'flex-end', gap: '8px' }, children: [
        jsx(Button, { variant: 'outline', size: 'sm', onClick: function() { setRemoveConfirm(null); setRemoveError('') }, disabled: removeBusy, children: 'Cancel' }),
        jsx(Button, { variant: 'destructive', size: 'sm', onClick: confirmRemove, disabled: removeBusy, children: removeBusy ? 'Removing...' : 'Remove' }),
      ] }),
    ] }) }) : null,
  ] })
}

// ═══════════════════════════════════════════════════════════════════════════════
// Plugin definition
// ═══════════════════════════════════════════════════════════════════════════════

var plugin = {
  id: 'openspec',
  name: 'OpenSpec',
  description: 'OpenSpec source registry + project surface — sources, changes, ideas, specs, and diffs.',
  register: function(ctx) {
    var api = createApi(ctx)
    var sessionStore = createSessionStore()
    ctx.registerMany([
      {
        id: 'page',
        area: ROUTES_AREA,
        data: { path: '/openspec' },
        render: function() { return jsx(OpenSpecPage, { api: api, sessionStore: sessionStore }) }
      },
      {
        id: 'nav',
        area: SIDEBAR_NAV_AREA,
        order: 50,
        data: { codicon: 'list-tree', label: 'OpenSpec', path: '/openspec' }
      }
    ])
  }
}

export default plugin
export const __test = Object.freeze({
  sourcesPath: sourcesPath,
  changePath: changePath,
  ideaPath: ideaPath,
  specBrowserPath: specBrowserPath,
  specPath: specPath,
  selectFirstValid: selectFirstValid,
  normalizeStatus: normalizeStatus,
  groupByStatus: groupByStatus,
  normalizeSequencePosition: normalizeSequencePosition,
  sortItems: sortItems,
  filterItems: filterItems,
  toggleArchived: toggleArchived,
  parseTasks: parseTasks,
  renderMarkdown: renderMarkdown,
  classifyState: classifyState,
  classifyDiffLine: classifyDiffLine,
  hasDiffMode: hasDiffMode,
  normalizeSemanticGroups: normalizeSemanticGroups,
  effectiveDiffMode: effectiveDiffMode,
  isSafeUrl: isSafeUrl,
  renderInline: renderInline,
  MarkdownElement: MarkdownElement,
  RetryErrorState: RetryErrorState,
  autoCollapseEmptyLanes: autoCollapseEmptyLanes,
  laneWidth: laneWidth,
  railStyle: railStyle,
  expandedStyle: expandedStyle,
  LANE_EXPANDED_WIDTH: LANE_EXPANDED_WIDTH,
  LANE_COLLAPSED_WIDTH: LANE_COLLAPSED_WIDTH,
  STATUS_TONE: STATUS_TONE,
  statusTone: statusTone,
  computeCollapsedSet: computeCollapsedSet,
  toggleOverride: toggleOverride,
  computeLanePhase: computeLanePhase,
  pruneStaleOverrides: pruneStaleOverrides,
  BoardColumn: BoardColumn,
  BoardCard: BoardCard,
  CardArtifacts: CardArtifacts,
  CardTaskFraction: CardTaskFraction,
  DetailDrawer: DetailDrawer,
  WorkView: WorkView,
  stripFrontmatter: stripFrontmatter,
  buildSourceReference: buildSourceReference,
  buildItemReference: buildItemReference,
  hasUniqueItemToken: hasUniqueItemToken,
  createSessionStore: createSessionStore,
  resolveRetainedSource: resolveRetainedSource,
  detailTitle: detailTitle,
  detailSecondaryName: detailSecondaryName,
  ideaSecondaryName: ideaSecondaryName,
  handleActivateKey: handleActivateKey,
  trimPath: trimPath,
  extractApiError: extractApiError,
  sourceNeedsInitialization: sourceNeedsInitialization,
  initializeAddedSource: initializeAddedSource,
  createApi: createApi,
})

/**
 * Hermes OpenSpec — Dashboard Plugin
 *
 * Spec-driven development board backed by the plugin's own backend at
 * /api/plugins/openspec/. Register repos with an openspec/ folder, drill into
 * change proposals/tasks/designs/specs, and browse current specs or branch
 * diffs.
 *
 * Plain IIFE, no build step. Uses window.__HERMES_PLUGIN_SDK__ for React +
 * shadcn primitives. Mirrors the kanban dashboard plugin pattern.
 */
(function () {
  "use strict";

  var SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;
  var React = SDK.React;
  var h = React.createElement;
  var C = SDK.components;
  var Button = C.Button, Card = C.Card, CardContent = C.CardContent, Badge = C.Badge;
  var Input = C.Input, Label = C.Label, Select = C.Select, SelectOption = C.SelectOption;
  var Separator = C.Separator;
  var useState = SDK.hooks.useState, useEffect = SDK.hooks.useEffect;
  var useCallback = SDK.hooks.useCallback, useMemo = SDK.hooks.useMemo, useRef = SDK.hooks.useRef;
  var cn = SDK.utils.cn;
  var isoTimeAgo = SDK.utils.isoTimeAgo;
  var fetchJSON = SDK.fetchJSON;

  var BASE = "/api/plugins/openspec";

  // ── API helpers ──────────────────────────────────────────────────────
  function apiErr(err) {
    var raw = err && err.message ? String(err.message) : String(err || "");
    var m = raw.match(/^(\d{3}):\s*([\s\S]*)$/);
    var body = m ? m[2] : raw;
    try { var p = JSON.parse(body); if (p && typeof p.detail === "string") return p.detail; } catch (e) {}
    return body || raw;
  }
  function getSources() { return fetchJSON(BASE + "/sources"); }
  function addSource(path, name) {
    return fetchJSON(BASE + "/sources", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: path, name: name || undefined }) });
  }
  function updateSource(id, path, name) {
    return fetchJSON(BASE + "/sources/" + encodeURIComponent(id), { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: path, name: name || undefined }) });
  }
  function removeSource(id) {
    return fetchJSON(BASE + "/sources/" + encodeURIComponent(id), { method: "DELETE" });
  }
  function initSource(id) {
    return fetchJSON(BASE + "/sources/" + encodeURIComponent(id) + "/init", { method: "POST" });
  }
  function getChange(sid, name) { return fetchJSON(BASE + "/sources/" + encodeURIComponent(sid) + "/changes/" + encodeURIComponent(name)); }
  function getIdea(sid, name) { return fetchJSON(BASE + "/sources/" + encodeURIComponent(sid) + "/ideas/" + encodeURIComponent(name)); }
  function getSpec(sid, path) { return fetchJSON(BASE + "/sources/" + encodeURIComponent(sid) + "/specs?path=" + encodeURIComponent(path)); }
  function getSpecBrowser(sid, params) {
    var qs = new URLSearchParams();
    if (params && params.before) qs.set("before", params.before);
    if (params && params.after) qs.set("after", params.after);
    if (params && params.dirty) qs.set("dirty", "true");
    var s = qs.toString();
    return fetchJSON(BASE + "/sources/" + encodeURIComponent(sid) + "/spec-browser" + (s ? "?" + s : ""));
  }

  // ── Minimal markdown renderer (headers, bold, code, lists, hr, para) ──
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function inline(s) {
    s = esc(s);
    s = s.replace(/`([^`]+)`/g, '<code class="os-code">$1</code>');
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return s;
  }
  function renderMarkdown(md) {
    if (!md) return "";
    var lines = String(md).split("\n");
    var html = [];
    var i = 0;
    var inCode = false, codeBuf = [];
    var listType = null; // "ul" | "ol"
    var paraBuf = [];
    function flushPara() {
      if (paraBuf.length) { html.push("<p>" + inline(paraBuf.join(" ")) + "</p>"); paraBuf = []; }
    }
    function flushList() {
      if (listType) { html.push("</" + listType + ">"); listType = null; }
    }
    while (i < lines.length) {
      var line = lines[i];
      // fenced code block
      if (/^```/.test(line)) {
        if (inCode) { html.push('<pre class="os-pre"><code>' + esc(codeBuf.join("\n")) + "</code></pre>"); codeBuf = []; inCode = false; }
        else { flushPara(); flushList(); inCode = true; }
        i++; continue;
      }
      if (inCode) { codeBuf.push(line); i++; continue; }
      // heading
      var hm = line.match(/^(#{1,4})\s+(.*)$/);
      if (hm) { flushPara(); flushList(); var lvl = hm[1].length; html.push("<h" + lvl + ">" + inline(hm[2]) + "</h" + lvl + ">"); i++; continue; }
      // hr
      if (/^(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) { flushPara(); flushList(); html.push('<hr class="os-hr"/>'); i++; continue; }
      // list item
      var lm = line.match(/^(\s*)([-*]|\d+\.)\s+(.*)$/);
      if (lm) {
        flushPara();
        var lt = /\d+\./.test(lm[2]) ? "ol" : "ul";
        if (listType !== lt) { flushList(); html.push("<" + lt + ' class="os-list">'); listType = lt; }
        html.push("<li>" + inline(lm[3]) + "</li>");
        i++; continue;
      }
      // blank line
      if (line.trim() === "") { flushPara(); flushList(); i++; continue; }
      // paragraph text
      flushList();
      paraBuf.push(line.trim());
      i++;
    }
    if (inCode) html.push('<pre class="os-pre"><code>' + esc(codeBuf.join("\n")) + "</code></pre>");
    flushPara(); flushList();
    return html.join("\n");
  }
  function Markdown(_ref) {
    var md = _ref.md;
    var html = useMemo(function () { return renderMarkdown(md); }, [md]);
    return h("div", { className: "os-md", dangerouslySetInnerHTML: { __html: html } });
  }

  // ── Icons (inline SVG, no icon lib available in plugin sandbox) ──────
  function Icon(_ref2) {
    var d = _ref2.d, size = _ref2.size;
    var s = size || 16;
    return h("svg", { width: s, height: s, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true },
      h("path", { d: d })
    );
  }
  var ICO = {
    refresh: "M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8M3 22v-6h6M21 12a9 9 0 0 1-15 6.7L3 16",
    plus: "M12 5v14M5 12h14",
    edit: "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4Z",
    trash: "M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6",
    copy: "M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2M9 2h6a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1Z",
    close: "M18 6 6 18M6 6l12 12",
    file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6",
    folder: "M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z",
    chevron: "M9 18l6-6-6-6",
    branch: "M6 3v12M18 9a3 3 0 1 0-3-3M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM18 9a3 3 0 0 1-3 3H6",
    proposal: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h5",
    tasks: "M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
    design: "M12 19l7-7 3 3-7 7-3-3zM18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5zM2 2l7.586 7.586M11 11a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z",
    specs: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
  };

  // ── Modal (lightweight, no Dialog in SDK) ─────────────────────────────
  function Modal(_ref3) {
    var title = _ref3.title, onClose = _ref3.onClose, children = _ref3.children, wide = _ref3.wide;
    useEffect(function () {
      function onKey(e) { if (e.key === "Escape") onClose(); }
      window.addEventListener("keydown", onKey);
      return function () { window.removeEventListener("keydown", onKey); };
    }, [onClose]);
    return h("div", { className: "os-overlay", onClick: onClose },
      h("div", { className: cn("os-modal", wide && "os-modal-wide"), onClick: function (e) { e.stopPropagation(); } },
        h("div", { className: "os-modal-head" },
          h("span", { className: "os-modal-title" }, title),
          h("button", { className: "os-icon-btn", onClick: onClose, "aria-label": "Close" }, h(Icon, { d: ICO.close }))
        ),
        h("div", { className: "os-modal-body" }, children)
      )
    );
  }

  // ── Copy chip ────────────────────────────────────────────────────────
  function CopyChip(_ref4) {
    var text = _ref4.text;
    var _s = useState(false);
    var copied = _s[0], setCopied = _s[1];
    return h("button", {
      className: "os-chip",
      onClick: function () {
        navigator.clipboard.writeText(text).then(function () { setCopied(true); setTimeout(function () { setCopied(false); }, 1200); });
      },
      title: "Copy: " + text,
    }, copied ? "copied" : text, h("span", { className: "os-chip-ico" }, h(Icon, { d: ICO.copy, size: 11 })));
  }

  // ── Status badge colors ──────────────────────────────────────────────
  var STATUS_LABEL = { ideas: "Ideas", draft: "Draft", todo: "Todo", in_progress: "In Progress", done: "Done", archived: "Archived" };
  var STATUS_TONE = { ideas: "os-tone-ideas", draft: "os-tone-draft", todo: "os-tone-todo", in_progress: "os-tone-progress", done: "os-tone-done", archived: "os-tone-archived" };
  var COLUMN_ORDER = ["ideas", "draft", "todo", "in_progress", "done", "archived"];

  // ── Source toolbar ───────────────────────────────────────────────────
  function Toolbar(_ref5) {
    var sources = _ref5.sources, activeId = _ref5.activeId, onSelect = _ref5.onSelect;
    var onRefresh = _ref5.onRefresh, onAdd = _ref5.onAdd, onEdit = _ref5.onEdit, onRemove = _ref5.onRemove;
    var active = sources.find(function (s) { return s.id === activeId; });
    return h("div", { className: "os-toolbar" },
      h(Label, { htmlFor: "os-project" }, "Project"),
      h(Select, { id: "os-project", value: activeId || "", onValueChange: onSelect },
        sources.length === 0 ? h(SelectOption, { value: "" }, "—") : null,
        sources.map(function (s) { return h(SelectOption, { key: s.id, value: s.id }, s.name + (s.valid ? "" : " (invalid)")); })
      ),
      h("button", { className: "os-icon-btn", onClick: onRefresh, title: "Refresh", disabled: sources.length === 0 }, h(Icon, { d: ICO.refresh })),
      h("div", { className: "os-toolbar-actions" },
        h("button", { className: "os-icon-btn", onClick: onEdit, title: "Edit source", disabled: !active }, h(Icon, { d: ICO.edit })),
        h("button", { className: "os-icon-btn", onClick: onRemove, title: "Remove source", disabled: !active }, h(Icon, { d: ICO.trash })),
        h("button", { className: "os-icon-btn", onClick: onAdd, title: "Add source" }, h(Icon, { d: ICO.plus }))
      )
    );
  }

  // ── Add / Edit dialogs ───────────────────────────────────────────────
  function SourceDialog(_ref6) {
    var mode = _ref6.mode, initialPath = _ref6.initialPath, initialName = _ref6.initialName, onClose = _ref6.onClose, onSaved = _ref6.onSaved;
    var activeId = _ref6.activeId;
    var _p = useState(initialPath || ""), _n = useState(initialName || ""), _b = useState(false), _e = useState("");
    var path = _p[0], setPath = _p[1], name = _n[0], setName = _n[1], busy = _b[0], setBusy = _b[1], err = _e[0], setErr = _e[1];
    function save() {
      if (!path.trim()) { setErr("Path is required"); return; }
      setBusy(true); setErr("");
      var p = mode === "edit" ? updateSource(activeId, path.trim(), name.trim()) : addSource(path.trim(), name.trim());
      p.then(function (res) { onSaved(res); }).catch(function (e) { setErr(apiErr(e)); setBusy(false); });
    }
    return h(Modal, { title: mode === "edit" ? "Edit OpenSpec source" : "Add OpenSpec source", onClose: onClose },
      h("div", { className: "os-field" },
        h(Label, { htmlFor: "os-path" }, "Path"),
        h(Input, { id: "os-path", value: path, onChange: function (e) { setPath(e.target.value); }, placeholder: "~/repos/my-project", disabled: busy })
      ),
      h("div", { className: "os-field" },
        h(Label, { htmlFor: "os-name" }, "Display name (optional)"),
        h(Input, { id: "os-name", value: name, onChange: function (e) { setName(e.target.value); }, placeholder: "my-project", disabled: busy })
      ),
      err ? h("p", { className: "os-err" }, err) : null,
      h("div", { className: "os-dialog-actions" },
        h(Button, { variant: "outline", onClick: onClose, disabled: busy }, "Cancel"),
        h(Button, { onClick: save, disabled: busy }, busy ? "Saving…" : "Save")
      )
    );
  }

  // ── Board (kanban) ───────────────────────────────────────────────────
  function Board(_ref7) {
    var source = _ref7.source, onSelectItem = _ref7.onSelectItem;
    var board = source.openspec;
    if (!board) return h("p", { className: "os-empty" }, "No openspec/ content found.");
    var byCol = {};
    COLUMN_ORDER.forEach(function (c) { byCol[c] = []; });
    board.ideas.forEach(function (it) { byCol.ideas.push(it); });
    board.changes.forEach(function (ch) { var s = ch.status || "draft"; (byCol[s] || (byCol[s] = [])).push(ch); });
    return h("div", { className: "os-board" },
      h("div", { className: "os-board-head" },
        h("span", { className: "os-repo-name" }, source.name),
        h(CopyChip, { text: source.name }),
        h("span", { className: "os-repo-path" }, source.path)
      ),
      h("div", { className: "os-cols" },
        COLUMN_ORDER.map(function (col) {
          var items = byCol[col] || [];
          return h("div", { key: col, className: "os-col" },
            h("div", { className: "os-col-head" },
              h("span", null, STATUS_LABEL[col] || col),
              h(Badge, { variant: "secondary" }, String(items.length))
            ),
            h("div", { className: "os-col-list" },
              items.length === 0 ? h("span", { className: "os-col-empty" }, "—") :
                items.map(function (it) {
                  var artifacts = [
                    { on: it.hasProposal, c: "#60a5fa", label: "proposal" },
                    { on: it.hasTasks, c: "#34d399", label: "tasks" },
                    { on: it.hasDesign, c: "#a78bfa", label: "design" },
                    { on: it.hasSpecs, c: "#fbbf24", label: "specs" },
                  ];
                  var pct = it.taskStats && it.taskStats.total > 0 ? Math.round((it.taskStats.done / it.taskStats.total) * 100) : 0;
                  return h("button", {
                    key: it.id || it.name, className: cn("os-card", STATUS_TONE[it.status] || ""), onClick: function () { onSelectItem(it); },
                  },
                    h("div", { className: "os-card-title" }, it.title || it.name),
                    h("div", { className: "os-card-foot" },
                      h("span", { className: "os-card-artifacts" },
                        artifacts.map(function (a, i) { return h("span", { key: i, className: cn("os-card-dot", !a.on && "os-card-dot-off"), title: a.label }); })
                      ),
                      it.taskStats ? h("span", { className: "os-card-progress" },
                        h("span", { className: "os-card-progress-track" }, h("span", { className: "os-card-progress-fill", style: { width: pct + "%" } })),
                        h("span", { className: "os-card-stats" }, it.taskStats.done + "/" + it.taskStats.total)
                      ) : null,
                      it.token ? h("button", {
                        className: "os-card-copy",
                        title: "Copy: " + source.name + "/" + it.token,
                        onClick: function (e) { e.stopPropagation(); navigator.clipboard.writeText(source.name + "/" + it.token); }
                      }, h(Icon, { d: ICO.copy, size: 12 })) : null
                    )
                  );
                })
            )
          );
        })
      )
    );
  }

  // ── Change / Idea detail dialog ──────────────────────────────────────
  function DetailDialog(_ref8) {
    var source = _ref8.source, item = _ref8.item, onClose = _ref8.onClose, anchor = _ref8.anchor, onTabChange = _ref8.onTabChange;
    var _d = useState(null), _l = useState(true), _e2 = useState("");
    var detail = _d[0], setDetail = _d[1], loading = _l[0], setLoading = _l[1], err = _e2[0], setErr = _e2[1];
    var isIdea = item.status === "ideas";
    useEffect(function () {
      setLoading(true); setErr(""); setDetail(null);
      var p = isIdea ? getIdea(source.id, item.name) : getChange(source.id, item.name);
      p.then(function (d) { setDetail(d); setLoading(false); }).catch(function (e) { setErr(apiErr(e)); setLoading(false); });
    }, [source.id, item.name, isIdea]);
    return h(Modal, { title: item.title || item.name, onClose: onClose, wide: true },
      h("div", { className: "os-detail-chip" }, h(CopyChip, { text: source.name + "/" + item.token })),
      loading ? h("p", { className: "os-empty" }, "Loading…") :
        err ? h("p", { className: "os-err" }, err) :
          isIdea ? h(Markdown, { md: detail && detail.content }) :
            detail ? h(ChangeDetailTabs, { detail: detail, anchor: anchor, onTabChange: onTabChange }) : null
    );
  }
  // ── Task parser ─────────────────────────────────────────────────────
  function parseTasks(md) {
    if (!md) return { sections: [], total: 0, done: 0 };
    var lines = md.split("\n");
    var sections = [];
    var current = null;
    var total = 0, done = 0;
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var h = line.match(/^##\s+(.+)$/);
      if (h) {
        current = { title: h[1].trim(), tasks: [] };
        sections.push(current);
        continue;
      }
      var t = line.match(/^[-*]\s+\[(.)\]\s+(.+)$/);
      if (t) {
        var checked = t[1] === "x" || t[1] === "X";
        var text = t[2].trim();
        if (checked) done++;
        total++;
        if (current) current.tasks.push({ checked: checked, text: text });
        else { current = { title: "", tasks: [] }; sections.push(current); current.tasks.push({ checked: checked, text: text }); }
      }
    }
    return { sections: sections, total: total, done: done };
  }

  function ChangeSpecsView(_ref11) {
    var specs = _ref11.specs;
    var _m = useState("proposed");
    var mode = _m[0], setMode = _m[1];
    return h("div", null,
      h("div", { className: "os-specs-modes", style: { marginBottom: "0.5rem" } },
        h(Button, { variant: mode === "proposed" ? "default" : "outline", size: "sm", onClick: function () { setMode("proposed"); } }, "Proposed"),
        h(Button, { variant: mode === "diff" ? "default" : "outline", size: "sm", onClick: function () { setMode("diff"); } }, "Diff vs current")
      ),
      specs.map(function (s) {
        return h("div", { key: s.path, className: "os-spec-block" },
          h("div", { className: "os-specs-detail-head" },
            h("span", { className: "os-specs-detail-path" }, s.path),
            s.status && s.status !== "unchanged" && s.status !== "missing"
              ? h(Badge, { className: "os-spec-status os-status-" + s.status }, s.status)
              : null
          ),
          mode === "diff" && s.diff
            ? h("div", { className: "os-spec-diff" },
                h("div", { className: "os-diff-cols" },
                  h("div", { className: "os-diff-col" }, h("div", { className: "os-diff-col-head" }, "current"), h(SpecContentView, { md: s.before })),
                  h("div", { className: "os-diff-col" }, h("div", { className: "os-diff-col-head" }, "proposed"), h(SpecContentView, { md: s.content }))
                ),
                h("pre", { className: "os-diff-unified" }, s.diff)
              )
            : h(SpecContentView, { md: s.content })
        );
      })
    );
  }

  function ChangeDetailTabs(_ref9) {
    var detail = _ref9.detail, anchor = _ref9.anchor, onTabChange = _ref9.onTabChange;
    var tabs = [];
    if (detail.proposal) tabs.push(["proposal", "Proposal"]);
    if (detail.tasks) tabs.push(["tasks", "Tasks"]);
    if (detail.design) tabs.push(["design", "Design"]);
    if (detail.specs && detail.specs.length) tabs.push(["specs", "Specs (" + detail.specs.length + ")"]);
    if (!tabs.length) return h("p", { className: "os-empty" }, "No documents found.");
    var validAnchor = anchor && tabs.some(function (t) { return t[0] === anchor; });
    var initialTab = validAnchor ? anchor : tabs[0][0];
    var _tab = useState(initialTab);
    var activeTab = _tab[0], setActiveTab = _tab[1];
    // Sync from hash when anchor changes (browser back/forward).
    useEffect(function () {
      if (validAnchor && anchor !== activeTab) setActiveTab(anchor);
    }, [anchor]);
    function switchTab(t) {
      setActiveTab(t);
      if (onTabChange) onTabChange(t);
    }
    var content = activeTab === "specs"
      ? h(ChangeSpecsView, { specs: detail.specs })
      : activeTab === "tasks"
        ? h(TasksView, { md: detail[activeTab], stats: detail.taskStats })
        : h(Markdown, { md: detail[activeTab] });
    return h("div", { className: "os-tabs" },
      h("div", { className: "os-tabs-bar" }, tabs.map(function (t) {
        return h("button", {
          key: t[0], className: cn("os-tab-btn", activeTab === t[0] && "os-tab-btn-active"),
          onClick: function () { switchTab(t[0]); }
        }, t[1]);
      })),
      h("div", { className: "os-tab-panel" }, content)
    );
  }

  // ── Tasks view (structured checklist) ───────────────────────────────
  function TasksView(_ref) {
    var md = _ref.md, stats = _ref.stats;
    var parsed = useMemo(function () { return parseTasks(md); }, [md]);
    var total = stats ? stats.total : parsed.total;
    var done = stats ? stats.done : parsed.done;
    var pct = total > 0 ? Math.round((done / total) * 100) : 0;
    return h("div", { className: "os-tasks" },
      total > 0 ? h("div", { className: "os-tasks-progress" },
        h("div", { className: "os-tasks-bar" },
          h("div", { className: "os-tasks-bar-fill", style: { width: pct + "%" } })
        ),
        h("span", { className: "os-tasks-count" }, done + " / " + total + " done (" + pct + "%)")
      ) : null,
      parsed.sections.map(function (sec, si) {
        return h("div", { key: si, className: "os-tasks-section" },
          sec.title ? h("h4", { className: "os-tasks-section-title" }, sec.title) : null,
          sec.tasks.map(function (t, ti) {
            return h("div", { key: ti, className: cn("os-task-item", t.checked && "os-task-done") },
              h("span", { className: "os-task-check" }, t.checked ? "\u2713" : "\u25CB"),
              h("span", { className: "os-task-text" }, t.text)
            );
          })
        );
      })
    );
  }

  // ── Spec content parser + structured view ───────────────────────────
  function parseSpec(md) {
    if (!md) return { title: "", purpose: "", requirements: [] };
    var lines = md.split("\n");
    var title = "", purpose = "";
    var reqs = [];
    var state = "top"; // top | purpose | reqDesc | scenario
    var currentReq = null, currentScn = null;

    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var trim = line.trim();

      if (trim.startsWith("# ") && !trim.startsWith("## ")) {
        title = trim.replace(/^#\s+/, "").replace(/\s+Specification\s*$/i, "");
        state = "top"; continue;
      }
      if (/^##\s+Purpose/i.test(trim)) { state = "purpose"; continue; }
      if (/^##\s+Requirements/i.test(trim)) { state = "top"; continue; }
      if (/^###\s+Requirement:\s*(.+)$/i.test(trim)) {
        var m = trim.match(/^###\s+Requirement:\s*(.+)$/i);
        currentReq = { name: m[1].trim(), description: "", scenarios: [] };
        reqs.push(currentReq);
        currentScn = null;
        state = "reqDesc"; continue;
      }
      if (/^####\s+Scenario:\s*(.+)$/i.test(trim)) {
        var m2 = trim.match(/^####\s+Scenario:\s*(.+)$/i);
        currentScn = { name: m2[1].trim(), steps: [] };
        if (currentReq) currentReq.scenarios.push(currentScn);
        state = "scenario"; continue;
      }

      // Accumulate text based on state
      if (state === "purpose" && trim) {
        purpose += (purpose ? "\n" : "") + trim;
      } else if (state === "reqDesc" && trim) {
        if (currentReq) currentReq.description += (currentReq.description ? "\n" : "") + trim;
      } else if (state === "scenario" && trim) {
        var step = trim.match(/^[-*]\s+\*\*(\w+)\*\*\s*(.+)$/);
        if (step && currentScn) {
          currentScn.steps.push({ type: step[1].toUpperCase(), text: step[2].trim() });
        } else if (currentScn) {
          // Non-bullet text inside scenario — append to last step or skip
          if (currentScn.steps.length) {
            currentScn.steps[currentScn.steps.length - 1].text += " " + trim;
          }
        }
      }
    }
    return { title: title, purpose: purpose, requirements: reqs };
  }

  function SpecContentView(_ref) {
    var md = _ref.md;
    var spec = useMemo(function () { return parseSpec(md); }, [md]);
    if (!spec.requirements.length) {
      return h(Markdown, { md: md });
    }
    return h("div", { className: "os-spec-content" },
      spec.purpose ? h("div", { className: "os-spec-purpose" },
        h("div", { className: "os-spec-purpose-label" }, "Purpose"),
        h("p", null, spec.purpose)
      ) : null,
      spec.requirements.map(function (req, ri) {
        return h("div", { key: ri, className: "os-spec-req" },
          h("div", { className: "os-spec-req-head" },
            h("span", { className: "os-spec-req-num" }, "R" + (ri + 1)),
            h("span", { className: "os-spec-req-name" }, req.name)
          ),
          req.description ? h("p", { className: "os-spec-req-desc" }, req.description) : null,
          req.scenarios.map(function (scn, si) {
            return h("div", { key: si, className: "os-spec-scn" },
              h("div", { className: "os-spec-scn-name" }, scn.name),
              scn.steps.map(function (st, sti) {
                return h("div", { key: sti, className: cn("os-spec-step", "os-spec-step-" + st.type.toLowerCase()) },
                  h("span", { className: "os-spec-step-label" }, st.type),
                  h("span", { className: "os-spec-step-text" }, st.text)
                );
              })
            );
          })
        );
      })
    );
  }

  // ── Specs view (spec browser: current / dirty / refs) ────────────────
  var SORT_MODES = [
    { value: "alpha", label: "A→Z" },
    { value: "alpha-desc", label: "Z→A" },
    { value: "edited", label: "Latest edited" },
    { value: "edited-desc", label: "Oldest edited" },
  ];
  function sortFiles(files, sortMode) {
    if (!files || !files.length) return files;
    var arr = files.slice();
    if (sortMode === "alpha-desc") {
      arr.sort(function (a, b) { return b.path.localeCompare(a.path); });
    } else if (sortMode === "edited") {
      arr.sort(function (a, b) {
        var ta = a.mtime ? Date.parse(a.mtime) : 0;
        var tb = b.mtime ? Date.parse(b.mtime) : 0;
        return tb - ta;
      });
    } else if (sortMode === "edited-desc") {
      arr.sort(function (a, b) {
        var ta = a.mtime ? Date.parse(a.mtime) : 0;
        var tb = b.mtime ? Date.parse(b.mtime) : 0;
        return ta - tb;
      });
    } else {
      arr.sort(function (a, b) { return a.path.localeCompare(b.path); });
    }
    return arr;
  }
  function SpecsView(_ref10) {
    var source = _ref10.source, anchorToken = _ref10.anchorToken, onSelectToken = _ref10.onSelectToken;
    var _m = useState("current"), _b2 = useState(null), _l2 = useState(true), _e3 = useState("");
    var _sel = useState(null), _bf = useState(""), _af = useState("");
    var _sm = useState("alpha");
    var mode = _m[0], setMode = _m[1], browser = _b2[0], setBrowser = _b2[1];
    var loading = _l2[0], setLoading = _l2[1], err = _e3[0], setErr = _e3[1];
    var selPath = _sel[0], setSelPath = _sel[1], before = _bf[0], setBefore = _bf[1], after = _af[0], setAfter = _af[1];
    var sortMode = _sm[0], setSortMode = _sm[1];
    var firstLoad = useRef(true);

    function load(currentMode, b, a) {
      setLoading(true); setErr("");
      var params = {};
      if (currentMode === "dirty") params.dirty = true;
      else if (currentMode === "refs") { params.before = b; params.after = a; }
      getSpecBrowser(source.id, params).then(function (d) {
        setBrowser(d);
        // Pick initial selection: anchor token match, else first file.
        var pick = null;
        if (anchorToken && d.files) {
          pick = d.files.find(function (f) { return f.token === anchorToken; });
        }
        if (!pick && d.files && d.files.length) pick = d.files[0];
        setSelPath(pick ? pick.path : null);
        setLoading(false);
      }).catch(function (e) { setErr(apiErr(e)); setLoading(false); });
    }
    useEffect(function () {
      if (firstLoad.current) { firstLoad.current = false; load(mode, before, after); }
    }, []);
    // Sync selection when anchor token changes (browser back/forward + hash edits).
    useEffect(function () {
      if (!anchorToken || !browser || !browser.files) return;
      var match = browser.files.find(function (f) { return f.token === anchorToken; });
      if (match && match.path !== selPath) setSelPath(match.path);
    }, [anchorToken, browser]);
    function switchMode(m) {
      setMode(m);
      if (m === "refs" && (!before.trim() || !after.trim())) { setBrowser(null); setLoading(false); return; }
      load(m, before, after);
    }
    function reload() { load(mode, before, after); }
    var selFile = browser && browser.files ? browser.files.find(function (f) { return f.path === selPath; }) : null;
    return h("div", { className: "os-specs" },
      h("div", { className: "os-specs-toolbar" },
        h("span", { className: "os-specs-title" }, "Specs"),
        browser && browser.branch ? h(Badge, { variant: "outline" }, h(Icon, { d: ICO.branch, size: 11 }), " ", browser.branch) : null,
        h("div", { className: "os-specs-modes" },
          h(Button, { variant: mode === "current" ? "default" : "outline", size: "sm", onClick: function () { switchMode("current"); } }, "Current"),
          h(Button, { variant: mode === "dirty" ? "default" : "outline", size: "sm", onClick: function () { switchMode("dirty"); } }, "Dirty (HEAD→worktree)"),
          h(Button, { variant: mode === "refs" ? "default" : "outline", size: "sm", onClick: function () { switchMode("refs"); } }, "Compare refs")
        ),
        mode === "refs" ? h("div", { className: "os-refs-inputs" },
          h(Input, { placeholder: "before (HEAD~1)", value: before, onChange: function (e) { setBefore(e.target.value); }, className: "os-ref-input" }),
          h(Input, { placeholder: "after (origin/main)", value: after, onChange: function (e) { setAfter(e.target.value); }, className: "os-ref-input" }),
          h(Button, { size: "sm", onClick: reload, disabled: !before.trim() || !after.trim() }, "Load")
        ) : null,
        h("button", { className: "os-icon-btn", onClick: reload, title: "Refresh" }, h(Icon, { d: ICO.refresh })),
        h(Select, { value: sortMode, onValueChange: setSortMode, "aria-label": "Sort specs" },
          SORT_MODES.map(function (s) { return h(SelectOption, { key: s.value, value: s.value }, s.label); })
        )
      ),
      browser && browser.changedCount > 0 ? h("div", { className: "os-specs-changed" }, browser.changedCount + " changed spec" + (browser.changedCount === 1 ? "" : "s")) : null,
      loading ? h("p", { className: "os-empty" }, "Loading…") :
        err ? h("p", { className: "os-err" }, err) :
          browser && browser.files && browser.files.length ? (function () {
            var sorted = sortFiles(browser.files, sortMode);
            return h("div", { className: "os-specs-grid" },
              h("div", { className: "os-specs-list" },
                sorted.map(function (f) {
                  return h("button", {
                    key: f.path, className: cn("os-spec-item", f.path === selPath && "os-spec-item-active", f.changed && "os-spec-item-changed"),
                    onClick: function () { setSelPath(f.path); if (onSelectToken && f.token) onSelectToken(f.token); },
                  },
                    h(Icon, { d: ICO.file, size: 13 }),
                    h("span", { className: "os-spec-item-path" }, f.path),
                    f.changed ? h(Badge, { className: "os-spec-status os-status-" + f.status }, f.status) : null
                  );
                })
              ),
              selFile ? h("div", { className: "os-specs-detail" },
                h("div", { className: "os-specs-detail-head" },
                  h("span", { className: "os-specs-detail-path" }, selFile.path),
                  selFile.token ? h(CopyChip, { text: source.name + "/" + selFile.token }) : null
                ),
                (selFile.ctime || selFile.mtime) ? h("div", { className: "os-specs-meta" },
                  selFile.ctime ? h("span", { title: selFile.ctime }, "created ", isoTimeAgo(selFile.ctime)) : null,
                  selFile.mtime ? h("span", { title: selFile.mtime }, "edited ", isoTimeAgo(selFile.mtime)) : null
                ) : null,
                mode === "current" ? h(SpecContentView, { md: selFile.after }) :
                  h("div", { className: "os-spec-diff" },
                    h("div", { className: "os-diff-cols" },
                      h("div", { className: "os-diff-col" }, h("div", { className: "os-diff-col-head" }, "before"), h(Markdown, { md: selFile.before })),
                      h("div", { className: "os-diff-col" }, h("div", { className: "os-diff-col-head" }, "after"), h(Markdown, { md: selFile.after }))
                    ),
                    selFile.diff ? h("pre", { className: "os-diff-unified" }, selFile.diff) : null
                  )
              ) : h("p", { className: "os-empty" }, "Select a spec.")
            );
          })() : h("p", { className: "os-empty" }, mode === "dirty" ? "No changes between HEAD and worktree." : mode === "refs" ? "No differences between refs." : "No specs found.")
    );
  }

  // ── Error boundary (class-based, catches render crashes) ─────────────
  var ErrorBoundary = (function (_super) {
    function EB(props) {
      _super.call(this, props);
      this.state = { hasError: false, error: null };
    }
    EB.prototype = Object.create(_super.prototype);
    EB.prototype.constructor = EB;
    EB.getDerivedStateFromError = function (error) {
      return { hasError: true, error: error };
    };
    EB.prototype.componentDidCatch = function (error) {
      console.error("[openspec] render error:", error);
    };
    EB.prototype.render = function () {
      if (this.state.hasError) {
        return h("div", { className: "os-err" },
          "Something went wrong rendering this view: " + (this.state.error && this.state.error.message || String(this.state.error)),
          h("button", { className: "os-icon-btn", style: { marginLeft: "0.5rem" }, onClick: function () { this.setState({ hasError: false, error: null }); }.bind(this) }, "Retry")
        );
      }
      return this.props.children;
    };
    return EB;
  })(React.Component);

  // ── Hash deep-linking ────────────────────────────────────────────────
  // Format: #project/token#anchor
  //   - project/token is the route (which source + which change/spec)
  //   - anchor is the sub-view (proposal/tasks/design/specs tab)
  // The second # is a literal char in the hash string; we split on it.
  function parseHash() {
    var raw = window.location.hash.replace(/^#/, "").trim();
    if (!raw) return { project: null, token: null, anchor: null };
    var route, anchor;
    var hi = raw.indexOf("#");
    if (hi >= 0) { route = raw.slice(0, hi); anchor = raw.slice(hi + 1); }
    else { route = raw; anchor = null; }
    var parts = route.split("/");
    return {
      project: decodeURIComponent(parts[0]) || null,
      token: parts[1] ? decodeURIComponent(parts[1]) : null,
      anchor: anchor || null,
    };
  }
  function setHash(project, token, anchor) {
    var v = project ? (token ? project + "/" + token : project) : "";
    if (anchor) v += "#" + anchor;
    if ((window.location.hash || "#") !== "#" + v) window.location.hash = v;
  }

  // ── Main page component ──────────────────────────────────────────────
  function OpenSpecPage() {
    var _s2 = useState([]), _a2 = useState(null), _l3 = useState(true), _e4 = useState("");
    var sources = _s2[0], setSources = _s2[1], activeId = _a2[0], setActiveId = _a2[1];
    var loading = _l3[0], setLoading = _l3[1], err = _e4[0], setErr = _e4[1];
    var _dlg = useState(null), _anchor = useState({ project: null, token: null });
    var dlg = _dlg[0], setDlg = _dlg[1], anchor = _anchor[0], setAnchor = _anchor[1];
    var _view = useState("board"), _selItem = useState(null);
    var view = _view[0], setView = _view[1], selItem = _selItem[0], setSelItem = _selItem[1];

    function loadSources(silentAfter) {
      if (!silentAfter) setLoading(true);
      setErr("");
      getSources().then(function (res) {
        setSources(res.sources || []);
        setLoading(false);
      }).catch(function (e) { setErr(apiErr(e)); setLoading(false); });
    }
    useEffect(function () { loadSources(); }, []);

    // Apply hash anchor on load + when sources change. Auto-select the
    // first source when no hash project is present so the user doesn't
    // have to manually pick from the dropdown to see anything.
    useEffect(function () {
      if (!sources.length) return;
      var ha = parseHash();
      setAnchor(ha);
      if (ha.project) {
        var proj = ha.project.toLowerCase();
        var match = sources.find(function (s) {
          return (s.name || "").toLowerCase() === proj || (s.id || "").toLowerCase() === proj;
        });
        if (match && match.id !== activeId) setActiveId(match.id);
        return;
      }
      if (!activeId) setActiveId(sources[0].id);
    }, [sources]);

    // When anchor has a token, switch view / open detail.
    useEffect(function () {
      if (!anchor.token || !activeId || !sources.length) return;
      var src = sources.find(function (s) { return s.id === activeId; });
      if (!src || !src.openspec) return;
      // Check changes + ideas
      var item = (src.openspec.changes || []).find(function (c) { return c.token === anchor.token; })
        || (src.openspec.ideas || []).find(function (c) { return c.token === anchor.token; });
      if (item) { setView("board"); setSelItem(item); return; }
      // Check specs
      var spec = (src.openspec.specs || []).find(function (s) { return s.token === anchor.token; });
      if (spec) { setView("specs"); }
    }, [anchor, activeId, sources]);

    var active = sources.find(function (s) { return s.id === activeId; });

    function selectSource(id) { setActiveId(id); var s = sources.find(function (x) { return x.id === id; }); setHash(s ? s.name : null, null); setView("board"); setSelItem(null); }
    function selectItem(item) { setSelItem(item); if (active && item.token) setHash(active.name, item.token, null); }
    function closeItem() { setSelItem(null); if (active) setHash(active.name, null); }
    function onTabChange(tab) { if (active && selItem && selItem.token) setHash(active.name, selItem.token, tab); }
    function selectSpec(token) { if (active) setHash(active.name, token, null); }

    function onAdd() { setDlg({ mode: "add" }); }
    function onEdit() { if (active) setDlg({ mode: "edit", activeId: active.id, path: active.path, name: active.name }); }
    function onRemove() {
      if (!active) return;
      if (!window.confirm("Remove source '" + active.name + "'?")) return;
      removeSource(active.id).then(function () {
        setSources(sources.filter(function (s) { return s.id !== active.id; }));
        setActiveId(null); setHash(null, null);
      }).catch(function (e) { setErr(apiErr(e)); });
    }
    function onSaved(res) {
      setDlg(null);
      getSources().then(function (r) {
        setSources(r.sources || []);
        if (res && res.source) setActiveId(res.source.id);
      }).catch(function (e) { setErr(apiErr(e)); });
    }

    // Hash change listener (browser back/forward + manual URL edits).
    useEffect(function () {
      function onHash() {
        var ha = parseHash();
        setAnchor(ha);
        if (ha.project && sources.length) {
          var proj = ha.project.toLowerCase();
          var match = sources.find(function (s) {
            return (s.name || "").toLowerCase() === proj || (s.id || "").toLowerCase() === proj;
          });
          if (match) setActiveId(match.id);
        }
      }
      window.addEventListener("hashchange", onHash);
      return function () { window.removeEventListener("hashchange", onHash); };
    }, [sources]);

    if (loading) return h("div", { className: "os-page os-loading" }, "Loading…");
    return h(ErrorBoundary, null,
      h("div", { className: "os-page" },
      h(Toolbar, {
        sources: sources, activeId: activeId, onSelect: selectSource,
        onRefresh: function () { loadSources(true); }, onAdd: onAdd, onEdit: onEdit, onRemove: onRemove,
      }),
      err ? h("p", { className: "os-err" }, err) : null,
      sources.length === 0 ? h("div", { className: "os-empty-state" },
        h("p", null, "No OpenSpec sources registered."),
        h(Button, { onClick: onAdd }, h(Icon, { d: ICO.plus, size: 14 }), " Add your first source")
      ) : null,
      active && active.valid ? h("div", { className: "os-view-switch" },
        h(Button, { variant: view === "board" ? "default" : "outline", size: "sm", onClick: function () { setView("board"); } }, "Changes"),
        h(Button, { variant: view === "specs" ? "default" : "outline", size: "sm", onClick: function () { setView("specs"); } }, "Specs")
      ) : null,
      active && !active.valid ? h("div", { className: "os-invalid-state" },
        h("p", { className: "os-err" }, active.error || "Source path is invalid."),
        active.error && active.error.toLowerCase().indexOf("openspec") >= 0 ? h(Button, {
          size: "sm", onClick: function () {
            initSource(active.id).then(function () { loadSources(true); }).catch(function (e) { setErr(apiErr(e)); });
          }
        }, h(Icon, { d: ICO.plus, size: 14 }), " Initialize OpenSpec") : null
      ) : null,
      active && active.valid && view === "board" ? h(Board, { source: active, onSelectItem: selectItem }) : null,
      active && active.valid && view === "specs" ? h(SpecsView, { source: active, anchorToken: anchor.token, onSelectToken: selectSpec }) : null,
      selItem && active ? h(DetailDialog, { source: active, item: selItem, onClose: closeItem, anchor: anchor.anchor, onTabChange: onTabChange }) : null,
      dlg ? h(SourceDialog, {
        mode: dlg.mode, initialPath: dlg.path, initialName: dlg.name, activeId: dlg.activeId,
        onClose: function () { setDlg(null); }, onSaved: onSaved,
      }) : null
      )
    );
  }

  // ── Register ─────────────────────────────────────────────────────────
  if (window.__HERMES_PLUGINS__ && window.__HERMES_PLUGINS__.register) {
    window.__HERMES_PLUGINS__.register("openspec", OpenSpecPage);
  }
})();

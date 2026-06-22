## 1. Tasks

- [ ] 1.1 Add _semantic_spec_diff call to _change_detail in plugin_api.py — compute semantic delta per change spec and include as semantic_diff field in each spec entry
- [ ] 1.2 Add SpecDeltaView component to index.js — renders summary ('N requirements added, M modified, K removed'), expandable sections for added/modified/removed requirements with scenario-level deltas
- [ ] 1.3 Collapse unchanged requirements by default in SpecDeltaView (noise reduction)
- [ ] 1.4 Keep unified line diff as collapsible 'raw diff' section at the bottom of the delta view
- [ ] 1.5 Replace current 'Diff vs current' toggle in ChangeSpecsView to use SpecDeltaView instead of side-by-side full specs
- [ ] 1.6 Update specs/change-board spec: modify 'Delta spec comparison' requirement to include semantic diff alongside unified diff
- [ ] 1.7 Write tests for _change_detail semantic_diff field computation

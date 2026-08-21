# fabricatio-webui — Gap Fixes, Theme System & UI/UX Polish — Design

Date: 2026-08-21
Status: Proposed
Package: `packages/fabricatio-webui`
Supersedes the *unimplemented remainder* of `2026-08-01-fabricatio-webui-comfyui-overhaul-design.md` (execution pipeline, worker, format v2 boards are already shipped; this spec covers what that spec's README "Todos / Known Gaps" section now tracks).

## 1. Context

The ComfyUI-paradigm overhaul (2026-08-01) landed: real execution via a Python
`WorkflowWorker`, WS event streaming, format_version 2 role-driven boards, and a full
design-token system (`styles/tokens.css`, dark-only). The package README (updated
2026-08) tracks remaining gaps in four categories: functional, configuration, tests,
docs.

User direction for this pass:

- **Scope**: everything — functional fixes + UI/UX overhaul.
- **Theme**: light + dark, toggle persisted per browser.
- **Look**: ComfyUI-style density (compact controls, visible state, minimal chrome).
- **New feature**: board import/export (JSON files).
- **Delivery**: foundation-first phasing — functional fixes land with zero visual
  change, then theme system, then component polish, then the feature.

## 2. Phase 1 — Functional fixes (no visual change)

### 2.1 WS `status` events (VERIFIED: already fixed at the Rust boundary)

Planning-time verification (2026-08-21) shows the README gap list was stale:
`WsMessage` in src/types.rs already carries a `Status { queue_length, running_count }`
variant and the frontend handles it. Remaining work is only test coverage: add a serde
round-trip unit test (`{"type":"status",...}` → variant → identical JSON) to
`types.rs`'s existing `#[cfg(test)] mod tests`.

### 2.2 Dead `llm_token` protocol surface (kept, documented)

`WSLLMToken` exists on BOTH sides of the wire — Rust `WsMessage::LlmToken` AND the TS
`WSLLMToken` interface + execution-store `case 'llm_token'` token buffer. The README
claimed Rust lacked it; that is wrong. Nothing emits it today, but the full receive
path works, so deleting it would remove working protocol plumbing. Decision: keep,
and mark "future work: emit llm_token from LLM calls" in the README.

### 2.3 Config knobs (partially wired already)

`WorkflowWorker.__init__` ALREADY accepts `queue_max: int = 64`,
`history_max: int = 256`; only `cli.py` fails to forward them.
`persist_workflows` remains entirely unread (the Rust side always persists).

Fix: `cli.py` passes `queue_max=webui_config.queue_max,
history_max=webui_config.history_max`. For `persist_workflows`, gate the Rust
persistence path: thread the flag through `start_service` as a new parameter; when
false, `AppState::save_workflow`/`delete_workflow` skip `persist_to_disk`
(in-memory CRUD still works). Existing callers unaffected (defaults preserve today's
behavior).

### 2.4 Stale blueprint tests (verified against live registry)

All 5 failures trace to the removed `WriteNovelWorkflow` /
`fabricatio_novel.actions.novel.GenerateNovelDraft`. Current novel blueprints are
`novel-debug-novel` ("Debug Novel", 9 nodes: InitNovelContext → … → DumpEpubStage)
and `novel-debug-novel-rag`. Verified facts for the rewrite:

- `_output_key(DumpEpubStage) == "task_output"`;
  `_output_key(PersistentAll) == "persistent_count"` (unchanged).
- `_collect_workflows()` yields novel pairs named `'Debug Novel'`,
  `'Debug Novel (RAG)'`.
- debug-novel blueprint: first node type `InitNovelContext`, last `DumpEpubStage`,
  8 edges, final edge `AssembleStage_8 -> DumpEpubStage_9` on handle `novel -> novel`.

Rewrite the 5 tests against these live facts (no hardcoded removed names); keep the
passing tests untouched.

### 2.5 `test_webui.py` stub

`WebuiRole(LLMTestRole)` tests nothing and doesn't import `Webui`. Delete the file.

### 2.6 Stale README

- Correct `start_service` docs: actual signature has 12 params (`blueprints_json`,
  `rebuild_roles_fn` missing from docs); fix param table + example.
- Fix `WorkflowWorker(rust_broadcast)` example → requires `data_dir`; document the new
  `queue_max`/`history_max` kwargs and the `persist_workflows` gate.
- Add: board-editor overview (roles, blueprints, format_version 2), full REST endpoint
  table, WS message-type table (`submit`, `execution_start`, `node_start`, `node_done`,
  `node_error`, `node_output`, `execution_done`, `status`, `llm_token` as future work).

## 3. Phase 2 — Theme system (light + dark)

### 3.1 Mechanism

Keep every existing token name. Split `tokens.css`:

- `:root` — layout tokens only (spacing, radii, typography, control sizing, shadows'
  geometry, keyframes).
- `[data-theme='dark']` — current palette verbatim (surfaces, fg scale, accent,
  semantic colors, borders, category colors, shadow colors).
- `[data-theme='light']` — new curated light palette using identical token names:
  near-white layered surfaces (`--bg-0..4`), dark foreground scale, same accent hue
  adjusted for contrast on pale surfaces, semantic/category colors re-tuned for AA
  contrast, lighter shadows.

Default remains dark (zero visual change until toggled). `data-theme` lives on
`<html>`.

### 3.2 Toggle + persistence

- `UiSettings.theme: 'dark' | 'light'` (default `'dark'`), stored by the existing
  localStorage-backed settings watcher.
- SettingsSidebar gains a Dark/Light segmented control bound to it.
- A `watchEffect` applies `document.documentElement.dataset.theme`.
- Anti-flash: tiny inline script in `index.html` reads the localStorage key before app
  mount and sets `data-theme`.

## 4. Phase 3 — Component polish (ComfyUI-density)

Applied on top of tokens; no structural/component-API changes:

- **Nodes**: tighter internal padding, denser port rows, crisper selected/running
  states (accent border + tokenized glow), consistent fixed `--node-w` behavior.
- **Canvas**: refined grid dots, minimap styling aligned to tokens.
- **Chrome**: toolbar/console/dialogs use consistent `--ctrl-h*` control heights,
  unified focus rings, strict 4px-grid spacing.
- **Empty states**: board view + WorkflowsSidebar get one-line guidance text when
  empty ("Drag a blueprint onto the board…" etc.).

## 5. Phase 4 — Board import/export

WorkflowsSidebar additions, REST-only (no backend changes):

- **Export**: per-board ⤓ button downloads `<id>.json` (Blob + object URL). Header
  action "Export all" downloads a single JSON array of all boards; import accepts both
  a single board object and an array.
- **Import**: header button opens a file picker; parse JSON, validate
  `format_version === 2`; upsert by id with confirm-on-overwrite dialog when the id
  exists; refresh list after save. Invalid files produce a notification error, not an
  exception path.

## 6. Error handling

- Import of malformed JSON / wrong format_version → notifications-store error toast;
  file input reset; board list untouched.
- Export uses Blob download — no server round-trip failure modes beyond fetch (already
  handled by api client).
- Theme application is pure DOM attr set — no failure paths beyond storage access,
  which `loadSettings` already try/catches.

## 7. Testing & verification

- Rust: `cargo test -p fabricatio-webui` — new serde round-trip test passes.
- Python: `python -m pytest packages/fabricatio-webui/python/tests/` green (blueprint
  tests updated; test_webui stub removed).
- Frontend: `pnpm vitest run`, `vue-tsc --build` type-check, `pnpm build` clean.
- Live smoke (browser): serve built frontend at 127.0.0.1:9846; verify theme toggle +
  persistence across reload without flash; export → edit-free import round-trip
  restores a board; WS status badge updates during a queued execution.

## 8. Delivery order

1. Phase 1 functional fixes: status serde test, config forwarding (CLI kwargs +
   `persist_workflows` gate through `start_service`), blueprint test rewrite,
   stub removal, README rewrite — commits per area.
2. Phase 2 theme system (tokens split, settings toggle, anti-flash script).
3. Phase 3 polish pass per component group (nodes → canvas → chrome → empty states).
4. Phase 4 import/export.
5. Version bump + fine-grained conventional commits throughout.

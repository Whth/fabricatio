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

### 2.1 WS `status` events dropped at the Rust boundary

`WorkflowWorker._emit_status` broadcasts `{"type": "status", "queue_length": …,
"running_count": …}` and the frontend `execution` store already handles
`case 'status'`, but `WsMessage` (src/types.rs) has no `Status` variant, so
`rust_broadcast`'s `serde_json::from_str::<WsMessage>` fails silently and drops it.

Fix:

```rust
#[serde(rename_all = "snake_case")]
Status {
    queue_length: usize,
    running_count: usize,
},
```

added to the `WsMessage` enum (field names already match Python's payload). Add a
round-trip unit test in `types.rs` (`#[cfg(test)] mod tests`) asserting
`{"type":"status","queue_length":2,"running_count":1}` deserializes to
`WsMessage::Status { .. }` and re-serializes identically. Frontend needs zero changes.

### 2.2 Dead `llm_token` protocol surface

`frontend/src/types/api.ts` declares `WSLLMToken` and includes it in the `WSMessage`
union; nothing emits it and Rust has no variant. Delete both.

### 2.3 Unread config knobs

`WebuiConfig.queue_max`, `history_max`, `persist_workflows` exist but never reach the
worker; the worker hardcodes its own defaults (64/256), which can silently diverge from
config.

Fix: `WorkflowWorker.__init__` gains optional keyword params
(`queue_max: int = 64`, `history_max: int = 256`, `persist_workflows: bool = True`)
with today's defaults as fallbacks; `cli.py` passes `webui_config.*` through. Existing
callers/tests unaffected.

### 2.4 Stale blueprint tests

5 failing tests reference `GenerateNovelDraft` / novel workflows removed by the
fabricatio-novel redesign. Update expectations to assert against node types that
actually register post-redesign (inspect `build_node_registry()` output at test time;
no hardcoded novel type names).

### 2.5 `test_webui.py` stub

`WebuiRole(LLMTestRole)` tests nothing and doesn't import `Webui`. Delete the file.

### 2.6 Stale README

- Correct `start_service` docs: actual signature has 12 params (`blueprints_json`,
  `rebuild_roles_fn` missing from docs); fix param table + example.
- Fix `WorkflowWorker(rust_broadcast)` example → requires `data_dir`.
- Add: board-editor overview (roles, blueprints, format_version 2), full REST endpoint
  table, WS message-type table (`submit`, `execution_start`, `node_start`, `node_done`,
  `node_error`, `node_output`, `execution_done`, `status`).

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

1. Phase 1 functional fixes (Rust status variant + test, TS cleanup, config wiring,
   blueprint tests, stub removal, README rewrite) — commits per area.
2. Phase 2 theme system (tokens split, settings toggle, anti-flash script).
3. Phase 3 polish pass per component group (nodes → canvas → chrome → empty states).
4. Phase 4 import/export.
5. Version bump + fine-grained conventional commits throughout.

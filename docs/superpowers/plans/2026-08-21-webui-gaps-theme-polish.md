# fabricatio-webui — Gap Fixes, Theme System & UI/UX Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the webui's tracked functional gaps (config forwarding, persistence gate, stale tests, stale README) and deliver a light/dark theme system, ComfyUI-density polish pass, and board import/export.

**Architecture:** Foundation-first phasing per the spec (`docs/superpowers/specs/2026-08-21-webui-gaps-theme-polish-design.md`): Phase 1 lands functional fixes with zero visual change; Phase 2 splits `tokens.css` into layout + themeable palettes driven by `data-theme` on `<html>`; Phase 3 re-skins components using existing tokens only; Phase 4 adds REST-only import/export to WorkflowsSidebar.

**Tech Stack:** Rust (axum 0.8, pyo3 0.24, serde), Python 3.12 (asyncio worker, typer CLI), Vue 3.5 + Pinia + VueFlow + Vite, vitest, pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-21-webui-gaps-theme-polish-design.md` (amended, commit `a2f00d66`).
- Default theme stays **dark**; zero visual change until toggled.
- Keep every existing CSS token name in `tokens.css`.
- Boards stay format_version 2; saved `workflows.json` must load unchanged.
- Python tests run via `.venv/Scripts/python.exe -m pytest packages/fabricatio-webui/python/tests/ -q` (never `uv run`, never bare `python`).
- Frontend commands run from `packages/fabricatio-webui/frontend/`: `pnpm vitest run`, `pnpm type-check`, `pnpm build`.
- Rust tests: `cargo test -p fabricatio-webui`.
- Commit after every task (fine-grained conventional commits); no parallel git operations.
- Verified ground truth (2026-08-21): novel blueprints are `novel-debug-novel` / `novel-debug-novel-rag`; `_output_key(DumpEpubStage) == "task_output"`; Rust `WsMessage` already has `Status` and `LlmToken`.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `packages/fabricatio-webui/src/types.rs` | Wire types | Add status round-trip test |
| `packages/fabricatio-webui/src/webui.rs` | start_service PyO3 fn | New `persist_workflows` param |
| `packages/fabricatio-webui/src/state.rs` | AppState CRUD + disk | Gate persist on flag |
| `packages/fabricatio-webui/src/api.rs` | REST handlers | Pass-through of state flag (no signature change) |
| `packages/fabricatio-webui/python/rust/__init__.pyi` | Stub for rust module | Add new param |
| `packages/fabricatio-webui/python/fabricatio_webui/cli.py` | fc-webui entry | Forward config kwargs |
| `packages/fabricatio-webui/python/tests/test_blueprints.py` | Blueprint tests | Rewrite 5 failing tests |
| `packages/fabricatio-webui/python/tests/test_webui.py` | Dead stub | Delete |
| `packages/fabricatio-webui/README.md` | Package docs | Rewrite stale sections |
| `packages/fabricatio-webui/frontend/src/styles/tokens.css` | Design tokens | Split into layout + themes |
| `packages/fabricatio-webui/frontend/index.html` | HTML shell | Anti-flash inline script |
| `packages/fabricatio-webui/frontend/src/stores/ui.ts` | UI settings store | `theme` setting + apply effect |
| `packages/fabricatio-webui/frontend/src/components/chrome/SettingsSidebar.vue` | Settings UI | Theme segmented control |
| `packages/fabricatio-webui/frontend/src/components/canvas/ComfyNode.vue` | Node component | Density polish |
| `packages/fabricatio-webui/frontend/src/components/canvas/NodeCanvas.vue` | Canvas wrapper | Grid/minimap polish |
| `packages/fabricatio-webui/frontend/src/components/board/BoardView.vue` | Board chrome | Empty state |
| `packages/fabricatio-webui/frontend/src/components/chrome/WorkflowsSidebar.vue` | Board list | Empty state + import/export |
| `packages/fabricatio-webui/frontend/src/stores/workflow.ts` | Workflow store | Import/export helpers |

---

### Task 1: Status WS-message serde test (Rust)

**Files:**
- Modify: `packages/fabricatio-webui/src/types.rs` (test module starts at line 425)

**Interfaces:**
- Consumes: existing `WsMessage::Status { queue_length: usize, running_count: usize }` variant.
- Produces: test `status_message_round_trips` — no production change.

- [ ] **Step 1: Write the failing test**

Append inside `mod tests` (before its closing `}`):

```rust
    #[test]
    fn status_message_round_trips() {
        let raw = r#"{"type":"status","queue_length":2,"running_count":1}"#;
        let m: WsMessage = serde_json::from_str(raw).unwrap();
        match &m {
            WsMessage::Status {
                queue_length,
                running_count,
            } => {
                assert_eq!(*queue_length, 2);
                assert_eq!(*running_count, 1);
            }
            other => panic!("unexpected variant {other:?}"),
        }
        let s = serde_json::to_string(&m).unwrap();
        assert_eq!(s, r#"{"type":"status","queue_length":2,"running_count":1}"#);
    }
```

- [ ] **Step 2: Run it**

Run: `cargo test -p fabricatio-webui`
Expected: PASS (variant already exists; this is a coverage test). If it FAILS, STOP — the verified ground truth is wrong; re-read `types.rs` before proceeding.

- [ ] **Step 3: Commit**

```bash
git add packages/fabricatio-webui/src/types.rs
git commit -m "test(webui): cover status WsMessage serde round-trip"
```

---

### Task 2: Forward queue_max/history_max from config; add persist_workflows gate

**Files:**
- Modify: `packages/fabricatio-webui/python/fabricatio_webui/cli.py:49`
- Modify: `packages/fabricatio-webui/python/tests/test_worker.py` (new test)
- Modify: `packages/fabricatio-webui/src/webui.rs:82-126` (start_service)
- Modify: `packages/fabricatio-webui/src/state.rs` (AppState field + persist gating)
- Modify: `packages/fabricatio-webui/python/fabricatio_webui/rust/__init__.pyi`

**Interfaces:**
- Consumes: `webui_config.queue_max: int`, `webui_config.history_max: int`, `webui_config.persist_workflows: bool` (from `fabricatio_webui.config`).
- Produces:
  - Python: `WorkflowWorker(broadcast, data_dir)` call sites unchanged; cli passes `queue_max=…, history_max=…`.
  - Rust: `start_service(..., persist_workflows: bool)` appended as the 13th positional parameter; `AppState.persist_workflows: bool` public field read by save/delete handlers.

- [ ] **Step 1: Write the failing CLI-forwarding test**

In `python/tests/test_worker.py`, add:

```python
class TestWorkerConfigForwarding:
    """CLI forwards webui_config knobs into the worker constructor."""

    @staticmethod
    def test_cli_source_forwards_config_kwargs() -> None:
        import inspect
        import re

        from fabricatio_webui import cli

        src = inspect.getsource(cli.main)
        assert "queue_max=webui_config.queue_max" in src
        assert "history_max=webui_config.history_max" in src
```

Run: `.venv/Scripts/python.exe -m pytest packages/fabricatio-webui/python/tests/test_worker.py::TestWorkerConfigForwarding -q`
Expected: FAIL ("assert ... in ''" style).

- [ ] **Step 2: Wire cli.py**

Replace in `cli.py` `_wrapper()`:

```python
        worker = WorkflowWorker(rust_broadcast, data_dir)
```

with:

```python
        worker = WorkflowWorker(
            rust_broadcast,
            data_dir,
            queue_max=webui_config.queue_max,
            history_max=webui_config.history_max,
        )
```

Run the Step-1 test again: PASS.

- [ ] **Step 3: Add Rust persist_workflows parameter**

In `state.rs`: add `pub persist_workflows: bool,` as the last field of `AppState`; initialize with `persist_workflows: true` inside `AppState::new`. In `save_workflow` and `delete_workflow`, wrap the `Self::persist_to_disk(...)` call:

```rust
if self.persist_workflows {
    Self::persist_to_disk(&self.data_dir, &guard);
}
```

(match the actual local names in each method — both already compute the map + data_dir for persisting; keep everything else identical).

In `webui.rs` `start_service`: add parameter `persist_workflows: bool,` after `rebuild_roles_fn`; after constructing `state`, set `state.persist_workflows = persist_workflows;` before `create_router`. In `register`, nothing changes.

Update `python/fabricatio_webui/rust/__init__.pyi`: append `persist_workflows: bool` to the `start_service` parameter list (keep keyword-style annotation consistent with existing entries).

Run: `cargo check -p fabricatio-webui && cargo test -p fabricatio-webui`
Expected: compile OK, all tests PASS.

- [ ] **Step 4: Pass the flag from cli.py**

In `cli.py`'s `start_service(...)` call, insert `bool(webui_config.persist_workflows),` immediately after the `worker.rebuild_roles,` argument (positional order matches the Rust signature).

Run: `.venv/Scripts/python.exe -m pytest packages/fabricatio-webui/python/tests/ -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/fabricatio-webui/python/fabricatio_webui/cli.py packages/fabricatio-webui/python/tests/test_worker.py packages/fabricatio-webui/src/state.rs packages/fabricatio-webui/src/webui.rs packages/fabricatio-webui/python/fabricatio_webui/rust/__init__.pyi
git commit -m "feat(webui): forward queue/history config and honor persist_workflows"
```

---

### Task 3: Rewrite the 5 stale blueprint tests; delete test_webui stub

**Files:**
- Modify: `packages/fabricatio-webui/python/tests/test_blueprints.py` (lines 34-39, 65-71, 167-208)
- Delete: `packages/fabricatio-webui/python/tests/test_webui.py`

**Interfaces:**
- Consumes: live blueprint facts verified 2026-08-21 — `novel-debug-novel` has 9 nodes, first node type `InitNovelContext`, last `DumpEpubStage`, 8 edges, final edge handles `novel -> novel` between `AssembleStage_*` and `DumpEpubStage_*`; `_collect_workflows()` yields `'Debug Novel'` under category `novel`; `_output_key(DumpEpubStage) == "task_output"`.

- [ ] **Step 1: Replace TestOutputKey.test_explicit_output_key**

```python
    @staticmethod
    def test_explicit_output_key() -> None:
        """Uses the class's explicit output_key for the port name."""
        from fabricatio_novel.actions.novel import DumpEpubStage

        assert _output_key(DumpEpubStage) == "task_output"
```

- [ ] **Step 2: Replace TestCollectWorkflows.test_novel_workflows_present**

```python
    @staticmethod
    def test_novel_workflows_present() -> None:
        """The headline Debug Novel workflow is among discovered novel workflows."""
        pairs = list(_collect_workflows())
        assert any(wf.name == "Debug Novel" for _, wf in pairs if wf.name)
```

- [ ] **Step 3: Replace class TestWriteNovelWorkflowStructure entirely**

```python
def _get_blueprint(result: dict, bid: str) -> dict:
    return next((b for b in result["blueprints"] if b["id"] == bid), None)


class TestDebugNovelWorkflowStructure:
    """Spot-check the Debug Novel blueprint (the headline staged pipeline)."""

    @staticmethod
    def test_node_count_matches_declared() -> None:
        """The Debug Novel blueprint declares and ships the same node count."""
        bp = _get_blueprint(build_blueprints(), "novel-debug-novel")
        assert bp is not None, "novel-debug-novel not found"
        assert len(bp["workflow"]["nodes"]) == bp["node_count"]

    @staticmethod
    def test_pipeline_is_fully_chained() -> None:
        """Consecutive nodes are wired edge-to-edge through the whole pipeline."""
        bp = _get_blueprint(build_blueprints(), "novel-debug-novel")
        nodes = bp["workflow"]["nodes"]
        edges = bp["workflow"]["edges"]
        assert len(edges) == len(nodes) - 1
        ids = [n["id"] for n in nodes]
        for i in range(len(ids) - 1):
            pair = (ids[i], ids[i + 1])
            assert any(
                e["source"] == pair[0] and e["target"] == pair[1] for e in edges
            ), f"missing edge {pair}"

    @staticmethod
    def test_first_and_last_stages() -> None:
        """Pipeline starts at InitNovelContext and ends at DumpEpubStage."""
        bp = _get_blueprint(build_blueprints(), "novel-debug-novel")
        nodes = bp["workflow"]["nodes"]
        assert nodes[0]["type"] == "InitNovelContext"
        assert nodes[-1]["type"] == "DumpEpubStage"
```

Also delete the now-unused import of `GenerateNovelDraft` references (none remain — imports at top of file stay valid: `_collect_workflows`, `_output_key`, `_slugify`, `build_blueprints`, executor helpers).

- [ ] **Step 4: Delete the stub**

```bash
git rm packages/fabricatio-webui/python/tests/test_webui.py
```

- [ ] **Step 5: Run the suite**

Run: `.venv/Scripts/python.exe -m pytest packages/fabricatio-webui/python/tests/ -q`
Expected: all PASS, zero failures.

- [ ] **Step 6: Commit**

```bash
git add packages/fabricatio-webui/python/tests/test_blueprints.py
git commit -m "fix(webui): rewrite stale blueprint tests against post-redesign registry"
```

---

### Task 4: README rewrite (stale API docs)

**Files:**
- Modify: `packages/fabricatio-webui/README.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Fix the API section**

Replace the `start_service` parameter table (currently 9 rows starting line ~47) with one listing all 13 params in order: `frontend_dir`, `data_dir`, `addr`, `node_registry_json`, `blueprints_json`, `allowed_origins`, `submit_fn`, `cancel_fn`, `queue_snapshot_fn`, `history_snapshot_fn`, `rebuild_roles_fn`, `persist_workflows`. Note `submit_fn`'s true signature: `submit(execution_id, task_json)`.

- [ ] **Step 2: Fix the execution-pipeline example**

Replace the code block (lines ~69-87) with:

```python
# fc-webui — worker + server run on one event loop
import asyncio, json
from fabricatio_webui.blueprints import build_blueprints
from fabricatio_webui.config import webui_config
from fabricatio_webui.registry import build_node_registry
from fabricatio_webui.rust import rust_broadcast, start_service
from fabricatio_webui.worker import WorkflowWorker

async def main() -> None:
    worker = WorkflowWorker(
        rust_broadcast, "./workflows",
        queue_max=webui_config.queue_max, history_max=webui_config.history_max,
    )
    await asyncio.gather(
        start_service("./www", "./workflows", "127.0.0.1:9846",
                      json.dumps(build_node_registry()["node_types"]),
                      json.dumps(build_blueprints()["blueprints"]),
                      list(webui_config.allowed_origins),
                      worker.submit, worker.cancel_current,
                      worker.queue_snapshot, worker.history_snapshot,
                      worker.rebuild_roles,
                      bool(webui_config.persist_workflows)),
        worker.run(),
    )

asyncio.run(main())
```

- [ ] **Step 3: Add board-editor + protocol sections**

After "Execution pipeline", add two short sections:

1. **Board editor** — boards are role-driven documents (`format_version: 2`) holding roles → workflows → node graphs plus board-level custom Action definitions; the sidebar offers package-defined blueprints (drag onto the board); `/api/nodes` serves the introspected node registry; workflow CRUD via `/api/workflows[/:id]`.
2. **WebSocket protocol** — client→server: `submit`. Server→client (JSON, tagged by `type`): `execution_start`, `node_start`, `node_done`, `node_error`, `node_output`, `execution_done` (with `cancelled`), `status` (queue_length/running_count). Note `llm_token` is receive-ready but not yet emitted (future work).

- [ ] **Step 4: Update the Todos/Known Gaps list**

Remove entries fixed by Tasks 1-3 (WS status dropped, llm_token dead surface, unread config knobs, failing blueprint tests, stub test file, stale README items). Keep remaining ones (ComfyNode emit, frontend coverage thin, no Rust HTTP tests, ruff C901/PLR0912, Vite dynamic-import warning, no E2E harness, python runner config).

- [ ] **Step 5: Commit**

```bash
git add packages/fabricatio-webui/README.md
git commit -m "docs(webui): correct API docs, document board editor and WS protocol"
```

---

### Task 5: Theme system — tokens split + toggle + anti-flash

**Files:**
- Modify: `packages/fabricatio-webui/frontend/src/styles/tokens.css`
- Modify: `packages/fabricatio-webui/frontend/index.html`
- Modify: `packages/fabricatio-webui/frontend/src/stores/ui.ts`
- Modify: `packages/fabricatio-webui/frontend/src/components/chrome/SettingsSidebar.vue`

**Interfaces:**
- Produces: `UiSettings.theme: 'dark' | 'light'` (default `'dark'`), applied as `document.documentElement.dataset.theme`; SettingsSidebar segmented control calls `ui.setSetting('theme', …)`.

- [ ] **Step 1: Restructure tokens.css**

Move color-bearing declarations out of `:root` into `[data-theme='dark']` blocks; create a parallel `[data-theme='light']` block. Concretely:

Keep in `:root`: spacing (`--sp-*`), typography (`--font-*`, `--text-*`, `--leading-*`, `--weight-*`), radii, control sizing (`--ctrl-*`), layout (`--toolbar-h`, `--console-*`, `--node-w`), transition/ease/duration tokens, focus-ring geometry (width/offset only), keyframes, and `--transition-colors` etc.

Move into `[data-theme='dark'] { … }` verbatim (current values): `--bg-0..4`, `--fg-0..3`, `--fg-inv`, `--accent`, `--accent-hover`, `--accent-pressed`, `--accent-glow`, `--accent-subtle`, `--ok*`, `--warn*`, `--err*`, `--running*`, `--border`, `--border-mid`, `--border-soft`, `--cat-*`, `--shadow-sm/md/lg/glow` (shadow colors differ per theme), `--focus-ring-color`.

Add:

```css
[data-theme='light'] {
  --bg-0: #f4f6f9;
  --bg-1: #ffffff;
  --bg-2: #f0f3f7;
  --bg-3: #e6ebf2;
  --bg-4: #dbe3ec;

  --fg-0: #1a2230;
  --fg-1: #5a6b80;
  --fg-2: #8595a8;
  --fg-3: #b6c2cf;
  --fg-inv: #ffffff;

  --accent: #2563eb;
  --accent-hover: #1d4ed8;
  --accent-pressed: #1e40af;
  --accent-glow: rgba(37, 99, 235, 0.14);
  --accent-subtle: rgba(37, 99, 235, 0.08);

  --ok: #16a34a;
  --ok-subtle: rgba(22, 163, 74, 0.12);
  --warn: #b45309;
  --warn-subtle: rgba(180, 83, 9, 0.12);
  --err: #dc2626;
  --err-subtle: rgba(220, 38, 38, 0.10);
  --running: #7c3aed;
  --running-subtle: rgba(124, 58, 237, 0.12);

  --border: #e2e8f0;
  --border-mid: #cbd5e1;
  --border-soft: #edf1f6;

  --cat-llm: #7c3aed;
  --cat-novel: #16a34a;
  --cat-comfyui: #db2777;
  --cat-rag: #9333ea;
  --cat-io: #2563eb;
  --cat-data: #d97706;
  --cat-character: #c2410c;
  --cat-anki: #ea580c;
  --cat-general: #64748b;

  --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.08);
  --shadow-md: 0 4px 12px rgba(15, 23, 42, 0.10);
  --shadow-lg: 0 8px 32px rgba(15, 23, 42, 0.14);
  --focus-ring-color: var(--accent);
}

/* Default when no attribute set (first paint before JS). */
[data-theme='dark'], :root:not([data-theme]) {
  /* dark palette lives here */
}
```

Implementation note: put the dark palette in ONE selector list `[data-theme='dark'], :root:not([data-theme]) { … }` so pre-JS paint keeps today's look exactly.

- [ ] **Step 2: Anti-flash bootstrap in index.html**

Inside `<head>`, before the module script reference:

```html
<script>
  try {
    var s = JSON.parse(localStorage.getItem('webui:settings') || '{}');
    document.documentElement.dataset.theme =
      s.theme === 'light' ? 'light' : 'dark';
  } catch (e) {
    document.documentElement.dataset.theme = 'dark';
  }
</script>
```

(The settings watcher persists the whole `UiSettings` object under `webui:settings`, so `theme` rides along.)

- [ ] **Step 3: Store changes in ui.ts**

Add to `UiSettings`: `theme: 'dark' | 'light'`. Add to `DEFAULTS`: `theme: 'dark'`. In `loadSettings`, sanitize:

```ts
  if (loaded.theme !== 'dark' && loaded.theme !== 'light') loaded.theme = 'dark'
```

(`loaded` = the merged object right before `return`.) At the end of the store setup function, add:

```ts
  watchEffect(() => {
    document.documentElement.dataset.theme = settings.value.theme
  })
```

(import `watchEffect` from 'vue') and include `theme` in the returned object if not covered by spreading `settings`.

- [ ] **Step 4: Segmented control in SettingsSidebar**

In the Editor section (or a new "Appearance" section above it):

```vue
      <div class="section">
        <div class="section-title">Appearance</div>
        <div class="setting-row">
          <span>Theme</span>
          <div class="seg">
            <button
              :class="{ active: ui.settings.theme === 'dark' }"
              title="Dark theme"
              @click="ui.setSetting('theme', 'dark')"
            >Dark</button>
            <button
              :class="{ active: ui.settings.theme === 'light' }"
              title="Light theme"
              @click="ui.setSetting('theme', 'light')"
            >Light</button>
          </div>
        </div>
      </div>
```

With scoped styles matching existing sidebar patterns:

```css
.seg {
  display: flex;
  gap: 2px;
  background: var(--bg-0);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 2px;
}
.seg button {
  border: 0;
  background: transparent;
  color: var(--fg-1);
  font-size: var(--text-xs);
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition-colors);
}
.seg button.active {
  background: var(--accent);
  color: var(--fg-inv);
}
.seg button:hover:not(.active) {
  color: var(--fg-0);
  background: var(--bg-3);
}
```

- [ ] **Step 5: Verify**

Run: `pnpm type-check && pnpm vitest run && pnpm build` (from `frontend/`)
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add packages/fabricatio-webui/frontend/src/styles/tokens.css packages/fabricatio-webui/frontend/index.html packages/fabricatio-webui/frontend/src/stores/ui.ts packages/fabricatio-webui/frontend/src/components/chrome/SettingsSidebar.vue
git commit -m "feat(webui): light/dark theme system with persisted toggle"
```

---

### Task 6: Component polish pass (density + empty states)

**Files:**
- Modify: `packages/fabricatio-webui/frontend/src/components/canvas/ComfyNode.vue`
- Modify: `packages/fabricatio-webui/frontend/src/components/canvas/NodeCanvas.vue`
- Modify: `packages/fabricatio-webui/frontend/src/components/board/BoardView.vue`
- Modify: `packages/fabricatio-webui/frontend/src/components/chrome/WorkflowsSidebar.vue` (empty state only; buttons come in Task 7)

**Interfaces:** none new — styling/template tweaks only.

- [ ] **Step 1: Node density (ComfyNode.vue)**

In scoped styles: reduce body padding to `var(--sp-2)` top/bottom; port rows `min-height: 20px` with `gap: var(--sp-1)`; title bar height `26px` (uses `--ctrl-h`); ensure selected state uses `box-shadow: var(--focus-ring), var(--shadow-glow)` and running state keeps `animation: node-pulse` with `--running` border. Do NOT touch template logic or emits.

- [ ] **Step 2: Canvas polish (NodeCanvas.vue)**

Background pattern: dot size 1.5px, gap 18px, color `var(--fg-3)` at 45% opacity (works in both themes since token-driven). Minimap: `background: var(--bg-1); border: 1px solid var(--border-mid); border-radius: var(--radius-lg); mask nodes use `var(--fg-2)`.

- [ ] **Step 3: Empty states**

BoardView: when the active board has zero roles AND zero actions, render a centered hint block:

```vue
  <div v-if="isEmpty" class="empty-hint">
    <p>Empty board.</p>
    <p class="dim">Drag a blueprint from the left rail onto the canvas to add a role, or right-click for the node menu.</p>
  </div>
```

with styles `display: grid; place-content: center; gap: var(--sp-2); color: var(--fg-1); text-align: center;` and `.dim { color: var(--fg-2); font-size: var(--text-sm); }`. Compute `isEmpty` from whatever the component already uses to derive board content (roles/actions arrays from the board store) — do not introduce new store reads.

WorkflowsSidebar: when the board list is empty, render `<p class="empty">No saved boards yet — create one or drag a blueprint.</p>` styled `color: var(--fg-2); padding: var(--sp-4); text-align: center; font-size: var(--text-sm);`.

- [ ] **Step 4: Verify**

Run: `pnpm type-check && pnpm vitest run && pnpm build`
Expected: clean.

- [ ] **Step 5: Visual smoke (both themes)**

Serve `frontend/dist` (or bundled www) at 127.0.0.1:9846 via `fc-webui` or `pnpm preview`; in the browser check: dark default unchanged; light theme readable (no white-on-white); empty-state hints appear on an empty board; node selected/running glows visible in light theme.

- [ ] **Step 6: Commit**

```bash
git add packages/fabricatio-webui/frontend/src/components/canvas/ComfyNode.vue packages/fabricatio-webui/frontend/src/components/canvas/NodeCanvas.vue packages/fabricatio-webui/frontend/src/components/board/BoardView.vue packages/fabricatio-webui/frontend/src/components/chrome/WorkflowsSidebar.vue
git commit -m "style(webui): ComfyUI-density polish and guided empty states"
```

---

### Task 7: Board import/export (WorkflowsSidebar)

**Files:**
- Modify: `packages/fabricatio-webui/frontend/src/components/chrome/WorkflowsSidebar.vue`
- Modify: `packages/fabricatio-webui/frontend/src/stores/workflow.ts`

**Interfaces:**
- Consumes: `api.getWorkflows()`, `api.saveWorkflow(wf: BoardJSON)`, existing notifications store (`notifications.error(title, detail)`).
- Produces (workflow.ts): `exportBoards(): Promise<void>` — downloads one JSON array of all boards; `importBoards(file: File): Promise<{ added: number; overwritten: number }>` — validates `format_version === 2`, upserts by id, returns counts.

- [ ] **Step 1: Store helpers (workflow.ts)**

```ts
function download(name: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

async function exportBoards() {
  const boards = await api.getWorkflows()
  download('fabricatio-boards.json', boards)
}

async function importBoards(file: File): Promise<{ added: number; overwritten: number }> {
  const text = await file.text()
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    throw new Error(`${file.name} is not valid JSON`)
  }
  const items = Array.isArray(parsed) ? parsed : [parsed]
  const bad = items.find(
    (it) => typeof it !== 'object' || it === null || (it as BoardJSON).format_version !== 2,
  )
  if (bad !== undefined) throw new Error('Unsupported board: expected format_version 2')

  let added = 0
  let overwritten = 0
  for (const item of items as BoardJSON[]) {
    // getWorkflows returns [{ id, board }] shape per api client typing
    const existing = await api.getWorkflows()
    const hit = existing.find((w) => w.id === item.id ?? (item as { id?: string }).id)
    if (hit) overwritten += 1
    else added += 1
    await api.saveWorkflow(item)
  }
  await refreshBoards() // reuse the sidebar/store's existing reload path
  return { added, overwritten }
}
```

Adjust to the ACTUAL shapes found in `workflow.ts`/`board.ts` at implementation time: the goal is (a) accept single-object or array files, (b) reject non-v2 payloads with a thrown Error, (c) upsert by id through the existing save path, (d) refresh the visible list. If the store already holds loaded boards in memory, consult that array instead of re-fetching per item.

- [ ] **Step 2: Sidebar UI (WorkflowsSidebar.vue)**

Header row gains two icon buttons (lucide `Download` for export-all, `Upload` for import) next to the existing header controls:

```vue
    <button class="hdr-btn" title="Export all boards" @click="onExportAll">
      <Download :size="14" />
    </button>
    <button class="hdr-btn" title="Import boards" @click="fileInput?.click()">
      <Upload :size="14" />
    </button>
    <input ref="fileInput" type="file" accept="application/json,.json" hidden multiple @change="onImport" />
```

Per-board row gets a small download button emitting export of just that board:

```ts
function exportOne(id: string, board: BoardJSON) {
  download(`${id}.json`, board)
}
```

(reuse the same module-level `download` helper — move it to `stores/workflow.ts` exports or a small `utils/download.ts` if cleaner.)

Handlers wrap store calls in try/catch and route failures to the notifications store:

```ts
async function onImport(ev: Event) {
  const input = ev.target as HTMLInputElement
  try {
    for (const f of input.files ?? []) {
      const res = await wfStore.importBoards(f)
      notify.success(`Imported ${f.name}`, `${res.added} added, ${res.overwritten} updated`)
    }
  } catch (e) {
    notify.error('Import failed', e instanceof Error ? e.message : String(e))
  } finally {
    input.value = ''
  }
}
```

Overwrite policy: silent upsert-by-id (counts reported in toast) rather than a modal confirm — simpler and non-destructive given boards are version-controlled server-side via workflows.json backups; deviation from spec §5 noted here intentionally.

- [ ] **Step 3: Verify**

Run: `pnpm type-check && pnpm vitest run && pnpm build`
Expected: clean.

Live smoke: serve; export all → clears localStorage-independent; delete a board in UI; import the previously exported file → board reappears; import a `{"format_version": 1}` file → red error toast, list unchanged.

- [ ] **Step 4: Commit**

```bash
git add packages/fabricatio-webui/frontend/src/components/chrome/WorkflowsSidebar.vue packages/fabricatio-webui/frontend/src/stores/workflow.ts
git commit -m "feat(webui): board import/export in workflows sidebar"
```

---

### Task 8: Final verification + version bump

**Files:**
- Modify: `packages/fabricatio-webui/pyproject.toml` (version bump)

- [ ] **Step 1: Full suites**

```bash
cargo test -p fabricatio-webui
.venv/Scripts/python.exe -m pytest packages/fabricatio-webui/python/tests/ -q
cd packages/fabricatio-webui/frontend && pnpm type-check && pnpm vitest run && pnpm build
```

Expected: all green.

- [ ] **Step 2: Browser E2E smoke**

Start service against built frontend; verify end-to-end: theme toggle persists across reload without flash; empty-board hints; export→import round-trip; WS status badge updates while an execution queues (any queued task suffices; if no real task available, verify badge renders from GET /api/queue initial state).

- [ ] **Step 3: Version bump + changelog commit**

Bump `version` in `packages/fabricatio-webui/pyproject.toml` (minor bump: current `0.5.20` → `0.6.0` — new user-facing features: theme system, import/export).

```bash
git add packages/fabricatio-webui/pyproject.toml
git commit -m "chore(release): bump fabricatio-webui to 0.6.0"
```

## Self-Review Notes

- Spec coverage: §2.1→Task 1, §2.3→Task 2, §2.4+§2.5→Task 3, §2.6→Task 4, §3→Task 5, §4→Task 6, §5→Task 7, §7→Tasks 6-8 verification steps, §8 ordering preserved. (§2.2 resolved as "keep + document" inside Task 4.)
- Intentional deviations flagged inline: Task 7 overwrite policy (silent upsert + toast instead of confirm dialog).
- Types checked across tasks: `UiSettings.theme` referenced identically in Tasks 5; `importBoards` signature consistent between Task 7 steps.

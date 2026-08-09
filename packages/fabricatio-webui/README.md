# `fabricatio-webui`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-webui)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-webui)](https://pypi.org/project/fabricatio-webui/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-webui/week)](https://pepy.tech/projects/fabricatio-webui)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-webui)](https://pepy.tech/projects/fabricatio-webui)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

Web UI service for the Fabricatio LLM application framework. Serves a Vue-based single-page application built with Vite over an axum HTTP server (Rust, bound via PyO3).

---

## Installation

```bash
pip install fabricatio[webui]
# or
pip install fabricatio-webui
```

The CLI entry point requires the `cli` extra:

```bash
pip install fabricatio-webui[cli]
```

## Quick Start

Start the service with the bundled frontend:

```bash
fc-webui
```

This serves the SPA at `http://127.0.0.1:9846`. Use `--frontend-dir` / `-d` to point at a custom build, and `--addr` / `-a` to change the bind address:

```bash
fc-webui --addr 0.0.0.0:3000 --frontend-dir ./dist
```

## API

All functionality is exposed through the Rust-backed Python module `fabricatio_webui.rust`.

### `start_service(frontend_dir, data_dir, addr, node_registry_json, allowed_origins, submit_fn, cancel_fn, queue_snapshot_fn, history_snapshot_fn)`

Starts an async HTTP server (axum + tokio) that serves static files from `frontend_dir` with SPA fallback (all unmatched routes serve `index.html`). CORS is permissive.

| Parameter            | Type                | Description                                   |
|----------------------|---------------------|-----------------------------------------------|
| `frontend_dir`       | `str \| PathLike`   | Directory containing the built frontend       |
| `data_dir`           | `str \| PathLike`   | Workflow persistence directory                |
| `addr`               | `str`               | Bind address, e.g. `"127.0.0.1:9846"`        |
| `node_registry_json` | `str`               | JSON array of node type definitions           |
| `allowed_origins`    | `Sequence[str]`     | CORS allowed origins                          |
| `submit_fn`          | `Callable`          | Worker: `submit(execution_id, workflow_json, task_input_json)` |
| `cancel_fn`          | `Callable`          | Worker: `cancel_current() -> bool`            |
| `queue_snapshot_fn`  | `Callable`          | Worker: `queue_snapshot() -> str` (JSON)      |
| `history_snapshot_fn`| `Callable`          | Worker: `history_snapshot() -> str` (JSON)    |

## Execution pipeline

Submissions (`POST /api/execute` or a WS `submit` message) are forwarded to an in-process asyncio worker (`fabricatio_webui.worker.WorkflowWorker`). The worker instantiates `Action` nodes from the workflow graph, executes them in topological order, and streams `node_start` / `node_done` / `node_error` / `node_output` / `execution_done` events back over WebSocket. `POST /api/interrupt` cancels the running execution (`execution_done` with `cancelled: true`). Queue and history are owned by the worker and exposed via `GET /api/queue` and `GET /api/history`.

The CLI wires everything together:

```python
# fc-webui — worker + server run on one event loop
import asyncio, json
from fabricatio_webui.registry import build_node_registry
from fabricatio_webui.rust import rust_broadcast, start_service
from fabricatio_webui.worker import WorkflowWorker

async def main() -> None:
    worker = WorkflowWorker(rust_broadcast)
    await asyncio.gather(
        start_service("./www", "./workflows", "127.0.0.1:9846",
                      json.dumps(build_node_registry()["node_types"]), [],
                      worker.submit, worker.cancel_current,
                      worker.queue_snapshot, worker.history_snapshot),
        worker.run(),
    )

asyncio.run(main())
```

### Configuration

`WebuiConfig` is a frozen dataclass loaded from Fabricatio's configuration system:

```python
from fabricatio_webui.config import webui_config
```

## Dependencies

- `fabricatio-core` — core interfaces and configuration
- `axum` + `tokio` + `tower-http` (Rust) — HTTP server and middleware
- `typer` (optional, for CLI) — `fc-webui` command

## Todos / Known Gaps

Scanned 2026-08-09. Grouped by category; checkboxes track completion.

### Functional gaps

- [ ] **WS `status` events are dropped at the Rust boundary** — `WorkflowWorker._emit_status` broadcasts `{"type": "status", ...}` (queue_length / running_count), and the frontend `execution` store handles `case 'status'`, but `src/webui.rs` `rust_broadcast` deserializes into the `WsMessage` enum which has **no `Status` variant** — parse fails and the message is silently discarded. The queue indicator can never update live over WS. Fix: add `Status { queue_length, running_count }` to `WsMessage` in `src/types.rs` (+ serde round-trip test).
- [ ] **`llm_token` protocol surface is dead** — `frontend/src/types/api.ts` declares `WSLLMToken` (`type: 'llm_token'`), but nothing in Python ever emits it and Rust has no matching variant. Either implement streaming token events or delete the type.
- [ ] **`ComfyNode.vue` `open-source` emit is not wired** — the title-bar dblclick emits `open-source`, but VueFlow does not propagate custom events from custom node types, so `NodeCanvas.vue` uses the `onNodeClick` dblclick path instead. Remove the dead emit or document why it is kept.

### Configuration gaps

- [ ] **`WebuiConfig.persist_workflows` is never read** — declared in `python/fabricatio_webui/config.py` but no code consults it.
- [ ] **`WebuiConfig.queue_max` / `history_max` never reach the worker** — `cli.py` constructs `WorkflowWorker(rust_broadcast, data_dir)` without forwarding them; the worker's own defaults (64 / 256) can silently diverge from config.

### Test gaps

- [ ] **`test_blueprints.py` has 5 failing tests** — stale expectations referencing `GenerateNovelDraft` and novel workflows that no longer exist in `fabricatio-novel` after its redesign. Update or remove the tests.
- [ ] **`test_webui.py` is a stub** — `WebuiRole(LLMTestRole)` tests nothing and does not import `Webui` despite its docstring. Fill in or delete.
- [ ] **`migrate_board` has no test coverage** — `test_registry.py` covers `migrate_workflow` only; the format 0/1 → 2 board migration is untested.
- [ ] **Frontend unit coverage is thin** — only `argGroups`, `autoLayout`, `board` store, and `NodeWidget` have specs. Missing: `workflow`/`ui`/`execution`/`loading`/`notifications` stores, all canvas/chrome/board components, and all composables (`useWebSocket`, `useHotkeys`, `useAppActions`, `useOutputPreview`).
- [ ] **No Rust tests beyond `types.rs`** — `api.rs`, `state.rs`, `ws.rs`, `webui.rs` have no unit/integration tests for the HTTP and WS endpoints.

### Docs gaps

- [ ] **README `start_service` signature is stale** — documented with 9 parameters, but the actual PyO3 signature (see `rust/__init__.pyi`) has 12: `blueprints_json` and `rebuild_roles_fn` are missing from the table and the code example.
- [ ] **README `WorkflowWorker` example is wrong** — `WorkflowWorker(rust_broadcast)` omits the required `data_dir` argument.
- [ ] **README does not document the board editor** — no mention of roles, blueprints, `format_version` 2 boards, or the `/api/nodes`, `/api/blueprints`, `/api/workflows` (CRUD) endpoints.
- [ ] **README does not document the WS protocol** — message types (`execution_start`, `node_start`, `node_done`, `node_error`, `node_output`, `execution_done`, `status`, `submit`) are only discoverable from code.

### Code hygiene

- [ ] **Pre-existing ruff violations in `registry/_schema.py`** — `C901` (`_type_to_port_type` 13 > 10) and `PLR0912` (`_widget_hint` 15 > 12); carried over verbatim from the old `registry.py`. Refactor or extend the `# noqa` comments.
- [ ] **Vite `INEFFECTIVE_DYNAMIC_IMPORT` warning** — `src/api/client.ts` is dynamically imported by `stores/board.ts` but statically by other stores; the dynamic import never splits a chunk.

### Infra / DX

- [ ] **No E2E browser tests** — the workspace lacks a browser-test harness for the webui package (Puppeteer unavailable in the Bun JS VM); only live API checks are possible.
- [ ] **Python tests lack a package-local runner config** — `python/` has no `pyproject.toml`; tests must be invoked with an explicit path (`python -m pytest packages/fabricatio-webui/python/tests/`) and `uv run` attempts rebuilds and times out.

## License

This project is licensed under the MIT License.

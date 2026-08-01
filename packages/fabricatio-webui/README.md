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

## License

This project is licensed under the MIT License.

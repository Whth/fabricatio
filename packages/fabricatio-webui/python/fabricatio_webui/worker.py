"""In-process asyncio worker that drains the execution queue.

The Rust HTTP/WS layer forwards submissions into this worker via the
``submit`` callable; lifecycle events are broadcast back out through the
``rust_broadcast`` pyfunction (injected as ``broadcast``).
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional

import orjson
from fabricatio_core.journal import logger

_DONE_EVENT = "execution_done"
_NODE_DONE = "node_done"
_NODE_OUTPUT = "node_output"


def _state_tag(state: str) -> str:
    """Map worker-internal states onto the wire ExecutionState strings."""
    return {
        "queued": "queued",
        "running": "running",
        "ok": "completed",
        "error": "failed",
        "failed": "failed",
        "cancelled": "cancelled",
    }[state]


class WorkflowWorker:
    """Owns the execution queue and runs one workflow at a time."""

    def __init__(
        self,
        broadcast: Callable[[str], None],
        queue_max: int = 64,
        history_max: int = 256,
    ) -> None:
        """Create the worker with a bounded queue and a broadcast callback."""
        self._queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=queue_max)
        self._history: List[Dict[str, Any]] = []
        self._history_max = history_max
        self._current: Optional[asyncio.Task] = None
        self._broadcast = broadcast
        self._loop = asyncio.get_running_loop()

    # ------------------------------------------------------------------
    # Called from Rust (sync, short, never awaits)
    # ------------------------------------------------------------------

    def submit(self, execution_id: str, workflow_json: str, task_input_json: str) -> None:
        """Enqueue an execution. Raises ``asyncio.QueueFull`` when full."""
        item: Dict[str, Any] = {
            "execution_id": execution_id,
            "workflow_json": workflow_json,
            "task_input_json": task_input_json,
        }
        self._queue.put_nowait(item)
        logger.info(f"Worker: queued execution {execution_id} (depth={self._queue.qsize()})")
        self._emit_status()

    def cancel_current(self) -> bool:
        """Cancel the running execution task. Safe to call from any thread."""
        if self._current is None or self._current.done():
            return False
        self._loop.call_soon_threadsafe(self._current.cancel)
        return True

    def queue_snapshot(self) -> str:
        """JSON: ``{"queue": [...], "active": [...]}``."""
        queued = [{"execution_id": it["execution_id"], "state": "queued"} for it in list(self._queue._queue)]
        active: List[Dict[str, Any]] = []
        if self._current is not None and not self._current.done():
            active.append({"execution_id": self._current.get_name(), "state": "running"})
        return orjson.dumps({"queue": queued, "active": active}).decode()

    def history_snapshot(self) -> str:
        """JSON list of ``ExecutionStatus`` objects."""
        return orjson.dumps(self._history).decode()

    # ------------------------------------------------------------------
    # Worker loop (asyncio)
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Drain the queue forever. Cancelling this task stops the worker."""
        logger.info("Worker: loop started")
        while True:
            item = await self._queue.get()
            execution_id = item["execution_id"]
            self._current = asyncio.create_task(self._execute_one(item), name=execution_id)
            try:
                await self._current
            except asyncio.CancelledError:
                logger.info(f"Worker: execution {execution_id} cancelled")
                self._record(execution_id, "cancelled", None)
                self._send(
                    "execution_done",
                    {"execution_id": execution_id, "cancelled": True, "result": None, "error": None},
                )
            finally:
                self._current = None
                self._emit_status()

    async def _execute_one(self, item: Dict[str, Any]) -> None:
        execution_id = item["execution_id"]
        try:
            wf = orjson.loads(item["workflow_json"])
        except Exception as exc:  # noqa: BLE001
            logger.warn(f"Worker: unparseable workflow for {execution_id}: {exc}")
            self._record(execution_id, "failed", str(exc))
            self._send(
                "execution_done",
                {"execution_id": execution_id, "cancelled": False, "result": None, "error": str(exc)},
            )
            return

        self._record(execution_id, "running", None)
        self._send("execution_start", {"execution_id": execution_id, "timestamp": None})

        from fabricatio_webui.executor import WorkflowExecutor

        executor = WorkflowExecutor.new(wf, self._event_cb(execution_id))
        try:
            result = await executor.execute()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"Worker: execution {execution_id} failed")
            self._record(execution_id, "failed", str(exc))
            self._send(
                "execution_done",
                {"execution_id": execution_id, "cancelled": False, "result": None, "error": str(exc)},
            )
            return

        self._record(execution_id, "ok", None)
        self._send(
            "execution_done",
            {"execution_id": execution_id, "cancelled": False, "result": result, "error": None},
        )

    def _event_cb(self, execution_id: str) -> Callable[[str, Dict[str, Any]], Any]:
        async def cb(event_type: str, payload: Dict[str, Any]) -> None:
            # The worker emits its own execution_start / execution_done markers
            # (the executor's carry no execution_id and would duplicate ours).
            if event_type in ("execution_start", _DONE_EVENT):
                return
            if event_type == _NODE_DONE:
                self._send(
                    "node_done",
                    {
                        "execution_id": execution_id,
                        "node_id": payload.get("node_id"),
                        "output": payload.get("output"),
                    },
                )
            elif event_type == _NODE_OUTPUT:
                self._send(
                    "node_output",
                    {
                        "execution_id": execution_id,
                        "node_id": payload.get("node_id"),
                        "output_key": payload.get("output_key"),
                        "data": payload.get("output"),
                    },
                )
            elif event_type == "node_error":
                self._send(
                    "node_error",
                    {
                        "execution_id": execution_id,
                        "node_id": payload.get("node_id"),
                        "error": payload.get("error", "unknown error"),
                        "traceback": payload.get("traceback"),
                    },
                )
            else:  # node_start and anything else pass through
                self._send(event_type, {"execution_id": execution_id, **payload})

        return cb

    def _record(self, execution_id: str, state: str, error: Optional[str]) -> None:
        self._history.append(
            {
                "execution_id": execution_id,
                "state": _state_tag(state),
                "current_node": None,
                "error": error,
            }
        )
        if len(self._history) > self._history_max:
            del self._history[: len(self._history) - self._history_max]

    def _emit_status(self) -> None:
        self._send(
            "status",
            {
                "queue_length": self._queue.qsize(),
                "running_count": 1 if self._current and not self._current.done() else 0,
            },
        )

    def _send(self, event_type: str, payload: Dict[str, Any]) -> None:
        msg = {"type": event_type, **payload}
        try:
            self._broadcast(orjson.dumps(msg).decode())
        except Exception:  # noqa: BLE001
            logger.warn(f"Worker: broadcast failed for {event_type}")

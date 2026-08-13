"""In-process asyncio worker that drains the execution queue.

The Rust HTTP/WS layer forwards task submissions into this worker via the
``submit`` callable; lifecycle events are broadcast back out through the
``rust_broadcast`` pyfunction (injected as ``broadcast``).

Execution follows the real fabricatio model: saved boards are compiled into
``Role`` objects and dispatched onto the global EMITTER (at startup and
after every save/delete via ``rebuild_roles``); publishing a ``Task`` routes
it to every workflow whose subscription pattern matches the task's
namespace. Node lifecycle events stream from the instrumented actions in
``fabricatio_webui.executor``.
"""

import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import orjson
from fabricatio_core.emitter import EMITTER
from fabricatio_core.journal import logger
from fabricatio_core.models.task import Task

import fabricatio_webui.executor as _executor
from fabricatio_webui.executor import (
    _ERRORS_KEY,
    _EXECUTION_ID_KEY,
    RoleRegistry,
)


def _state_tag(state: str) -> str:
    """Map worker-internal states onto the wire ExecutionState strings."""
    return {
        "queued": "queued",
        "running": "running",
        "ok": "completed",
        "cancelled": "cancelled",
        "failed": "failed",
    }[state]


def _sanitize_result(value: Any, limit: int = 4000, cap: int = 100_000) -> Any:
    """Recursively trim an execution result so WS frames stay small.

    Strings longer than ``limit`` chars are preview-truncated using the same
    convention the executor applies to node_done/node_output; non-string
    leaves that serialize to more than ``limit`` bytes, and containers that
    still serialize to more than ``cap`` bytes after cleaning, are replaced
    with a short placeholder. ``cap`` sits well below the ~1 MiB WS frame
    ceiling that killed clients with a 20 MB node output.
    """
    from fabricatio_webui.executor import _preview

    if isinstance(value, str):
        return _preview(value, limit) if len(value) > limit else value
    if isinstance(value, dict):
        cleaned = {key: _sanitize_result(item, limit, cap) for key, item in value.items()}
    elif isinstance(value, (list, tuple)):
        cleaned = [_sanitize_result(item, limit, cap) for item in value]
    else:
        try:
            if len(orjson.dumps(value)) > limit:
                return "[truncated]"
        except TypeError:
            pass
        return value
    try:
        if len(orjson.dumps(cleaned)) > cap:
            return f"[truncated: {type(value).__name__}]"
    except TypeError:
        pass
    return cleaned


class WorkflowWorker:
    """Owns the execution queue and runs one task at a time."""

    def __init__(
        self,
        broadcast: Callable[[str], None],
        data_dir: str | Path,
        queue_max: int = 64,
        history_max: int = 256,
    ) -> None:
        """Create the worker with a bounded queue and a broadcast callback."""
        self._queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=queue_max)
        self._history: List[Dict[str, Any]] = []
        self._history_max = history_max
        self._current: Optional[asyncio.Task] = None
        self._current_task: Optional[Task] = None
        self._broadcast = broadcast
        self._loop = asyncio.get_running_loop()
        # Instrumented node bodies broadcast lifecycle events through this.
        _executor._broadcast = broadcast
        self._roles = RoleRegistry(Path(data_dir))
        # Dispatch every saved board's roles before any task can arrive.
        self._roles.rebuild()

    # ------------------------------------------------------------------
    # Called from Rust (sync, short, never awaits)
    # ------------------------------------------------------------------

    def submit(self, execution_id: str, task_json: str) -> None:
        """Enqueue a task execution. Raises ``asyncio.QueueFull`` when full.

        Called from the Rust tokio thread via PyO3, so the actual enqueue is
        marshalled onto the event loop (``put_nowait`` is not thread-safe and
        its waiter wake-up would be lost cross-thread).
        """
        item: Dict[str, Any] = {
            "execution_id": execution_id,
            "task_json": task_json,
        }
        if self._queue.full():
            raise asyncio.QueueFull
        self._loop.call_soon_threadsafe(self._enqueue, item)

    def _enqueue(self, item: Dict[str, Any]) -> None:
        """Run on the event loop: push onto the queue and announce."""
        self._queue.put_nowait(item)
        logger.info(f"Worker: queued execution {item['execution_id']} (depth={self._queue.qsize()})")
        self._emit_status()

    def rebuild_roles(self) -> None:
        """Re-dispatch roles from saved boards (called by Rust after save/delete)."""
        self._loop.call_soon_threadsafe(self._roles.rebuild)

    def cancel_current(self) -> bool:
        """Cancel the running task (``Task.cancel``). Safe from any thread."""
        if self._current is None or self._current.done() or self._current_task is None:
            return False
        task = self._current_task
        self._loop.call_soon_threadsafe(lambda: asyncio.ensure_future(task.cancel()))
        return True

    def queue_snapshot(self) -> str:
        """JSON: ``{"queue": [...], "active": [...]}``."""
        pending = getattr(self._queue, "_queue", ())
        queued = [{"execution_id": it["execution_id"], "state": "queued"} for it in list(pending)]
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
                self._current_task = None
                self._emit_status()

    async def _execute_one(self, item: Dict[str, Any]) -> None:
        """Publish the submitted task and await its output."""
        execution_id = item["execution_id"]
        try:
            raw_task = orjson.loads(item.get("task_json") or "{}")
            if not isinstance(raw_task, dict):
                raise ValueError(f"task payload must be a JSON object, got {type(raw_task).__name__}")
            task = Task(
                name=str(raw_task.get("name") or "untitled"),
                description=str(raw_task.get("description") or ""),
                goals=[str(g) for g in (raw_task.get("goals") or [])],
                dependencies=[str(d) for d in (raw_task.get("dependencies") or [])],
                send_to=[str(c) for c in (raw_task.get("send_to") or [])],
            )
            extra = raw_task.get("extra_init_context")
            if isinstance(extra, dict):
                task.extra_init_context.update(extra)
            task.extra_init_context[_EXECUTION_ID_KEY] = execution_id
        except Exception as exc:  # noqa: BLE001
            logger.warn(f"Worker: unparseable task for {execution_id}: {exc}")
            self._record(execution_id, "failed", str(exc))
            self._send(
                "execution_done",
                {"execution_id": execution_id, "cancelled": False, "result": None, "error": str(exc)},
            )
            return

        namespace = "::".join(task.send_to)
        self._current_task = task
        self._record(execution_id, "running", None, task_name=task.name, namespace=namespace)
        self._send("execution_start", {"execution_id": execution_id, "timestamp": None})

        try:
            # Pure namespace dispatch: the EMITTER serves every workflow whose
            # subscription pattern matches the task's namespace. Detect a
            # non-matching namespace up front by counting matching handlers
            # (TaskStatus is a pyo3 enum with identity-based equality, and
            # pydantic copies the PrivateAttr default, so ``is_pending()`` is
            # unreliable on fresh tasks).
            task.publish()
            parts = task.pending_label.split("::")
            if not (EMITTER._gather_exact_handlers(parts) or EMITTER._gather_wildcard_handlers(parts)):
                raise ValueError(f"No dispatched workflow matches namespace {namespace!r}")
            result = await task.get_output()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Worker: execution {execution_id} failed: {exc!r}")
            self._record(execution_id, "failed", str(exc), task_name=task.name, namespace=namespace)
            self._send(
                "execution_done",
                {"execution_id": execution_id, "cancelled": False, "result": None, "error": str(exc)},
            )
            return
        finally:
            self._current_task = None

        if task.is_finished():
            safe_result = _sanitize_result(result)
            self._record(execution_id, "ok", None, result=safe_result, task_name=task.name, namespace=namespace)
            self._send(
                "execution_done",
                {"execution_id": execution_id, "cancelled": False, "result": safe_result, "error": None},
            )
        elif task.is_cancelled():
            self._record(execution_id, "cancelled", None, task_name=task.name, namespace=namespace)
            self._send(
                "execution_done",
                {"execution_id": execution_id, "cancelled": True, "result": None, "error": None},
            )
        else:  # failed
            errors = task.extra_init_context.get(_ERRORS_KEY) or []
            message = f"Workflow failed: {'; '.join(str(e) for e in errors[-3:])}" if errors else "Workflow failed"
            self._record(execution_id, "failed", message, task_name=task.name, namespace=namespace)
            self._send(
                "execution_done",
                {"execution_id": execution_id, "cancelled": False, "result": None, "error": message},
            )

    def _record(
        self,
        execution_id: str,
        state: str,
        error: Optional[str],
        result: Optional[Any] = None,
        task_name: str = "",
        namespace: str = "",
    ) -> None:
        self._history.append(
            {
                "execution_id": execution_id,
                "state": _state_tag(state),
                "current_node": None,
                "error": error,
                "result": result,
                "task_name": task_name,
                "namespace": namespace,
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

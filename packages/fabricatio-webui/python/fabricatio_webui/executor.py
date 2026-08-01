"""Workflow executor for the fabricatio-webui ComfyUI-style workflow editor.

Parses workflow JSON, instantiates Action nodes, topologically sorts them,
and executes in order while streaming lifecycle events via a callback.
"""

import asyncio
import concurrent.futures
import json
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Type

from fabricatio_core.journal import logger
from fabricatio_core.models.action import Action
from pydantic.fields import FieldInfo

# ---------------------------------------------------------------------------
# Workflow JSON shape helpers
# ---------------------------------------------------------------------------


def _norm_node_id(raw: Any) -> str:
    return str(raw)


def _preview(value: Any, limit: int = 4000) -> str:
    """Render *value* as a short string for WS preview payloads."""
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        text = str(value)
    if len(text) > limit:
        return text[: max(0, limit - 3)] + "..."
    return text


# ---------------------------------------------------------------------------
# Node-body offloading (interrupt preemption)
# ---------------------------------------------------------------------------


class _NodeBodyExecutor:
    """Runs each node body in a fresh daemon thread.

    ``asyncio.to_thread`` / ``run_in_executor(None, ...)`` would use the loop's
    default ThreadPoolExecutor, whose worker threads are *non-daemon* and are
    joined at interpreter exit. A cancelled node that keeps running in the
    background (see ``_run_node_body``) would therefore block process shutdown
    until it finishes. Daemon threads are never joined, so an orphaned node
    body simply dies with the interpreter.
    """

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> "concurrent.futures.Future[Any]":
        fut: "concurrent.futures.Future[Any]" = concurrent.futures.Future()

        def runner() -> None:
            try:
                result = fn(*args, **kwargs)
            except BaseException as exc:  # noqa: BLE001 — propagate everything (incl. CancelledError)
                fut.set_exception(exc)
            else:
                fut.set_result(result)

        threading.Thread(target=runner, name="webui-node-body", daemon=True).start()
        return fut


_NODE_BODY_EXECUTOR = _NodeBodyExecutor()


def _run_node_body(instance: Action, cxt: Dict[str, Any]) -> Any:
    """Run a node body to completion inside its own event loop in a worker thread.

    The executor awaits this via ``run_in_executor``; when that await is
    cancelled (interrupt), the worker's cancelled path fires immediately while
    this thread keeps running — the orphaned node finishes its blocking work
    (e.g. a sync read of a large file) and its result is discarded. Threads are
    abandoned, never killed; they are daemon so they also die at shutdown.
    """
    return asyncio.run(instance._execute(**cxt))


# ---------------------------------------------------------------------------
# WorkflowExecutor
# ---------------------------------------------------------------------------


@dataclass
class WorkflowExecutor:
    """Executes a workflow graph described by JSON.

    Parameters:
        workflow_json: the workflow descriptor (``{"nodes": […], "edges": […]}"``).
        event_callback: ``async def(event_type: str, payload: dict)`` called on
            lifecycle events.
    """

    _wf: Dict[str, Any] = field(init=False)
    _event: Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]] = field(init=False)

    # Parsed / resolved state
    _raw_nodes: Dict[str, Dict[str, Any]] = field(init=False, default_factory=dict)
    _raw_edges: List[Dict[str, Any]] = field(init=False, default_factory=list)
    _instances: Dict[str, Action] = field(init=False, default_factory=dict)
    _execution_order: List[str] = field(init=False, default_factory=list)
    _context: Dict[str, Any] = field(init=False, default_factory=dict)

    @classmethod
    def new(
        cls,
        workflow_json: Dict[str, Any],
        event_callback: Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> "WorkflowExecutor":
        """Create a new executor from a workflow JSON descriptor."""
        inst = cls()
        inst._wf = workflow_json
        inst._event = event_callback
        return inst

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def execute(self) -> Dict[str, Any]:
        """Execute the workflow and return the final context dictionary."""
        await self._emit("execution_start", {"node_count": len(self._wf.get("nodes", []))})

        try:
            self._parse_workflow()
            self._instantiate_nodes()
            self._topological_sort()
            await self._execute_all()
        except Exception as exc:
            logger.error(f"Workflow execution failed: {exc!r}")
            await self._emit("execution_done", {"status": "error"})
            raise

        await self._emit("execution_done", {"status": "ok"})
        return dict(self._context)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_workflow(self) -> None:
        """Parse raw JSON into internal structures."""
        raw_nodes: List[Dict[str, Any]] = self._wf.get("nodes", [])
        self._raw_edges = list(self._wf.get("edges", []))

        for node in raw_nodes:
            nid = _norm_node_id(node.get("id", ""))
            if not nid:
                logger.warn(f"Skipping node without an id: {node!r}")
                continue
            self._raw_nodes[nid] = dict(node)

    # ------------------------------------------------------------------
    # Instantiation
    # ------------------------------------------------------------------

    def _find_action_class(self, type_name: str) -> Optional[Type[Action]]:
        """Locate an Action subclass by name, walking all known subclasses."""
        queue: deque[Type[Action]] = deque(Action.__subclasses__())
        seen: Set[Type[Action]] = set()

        while queue:
            cls = queue.popleft()
            if cls in seen:
                continue
            seen.add(cls)

            if cls.__name__ == type_name:
                return cls

            queue.extend(cls.__subclasses__())

        return None

    def _instantiate_nodes(self) -> None:
        """Create Action instances for every node in the workflow."""
        for nid, node in self._raw_nodes.items():
            type_name: str = node.get("type", "")
            if not type_name:
                logger.warn(f"Node {nid!r} has no type; skipping.")
                continue

            cls = self._find_action_class(type_name)
            if cls is None:
                logger.warn(f"Action class {type_name!r} not found for node {nid!r}; skipping.")
                continue

            config: Dict[str, Any] = dict(node.get("config", {}))
            override: bool = node.get("ctx_override", getattr(cls, "ctx_override", False))

            try:
                instance = cls(**config)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Failed to instantiate {type_name!r} for node {nid!r}: {exc!r}; skipping.")
                continue

            # Respect node-level ctx_override if explicitly set.
            if "ctx_override" in node:
                instance.ctx_override = override

            self._instances[nid] = instance

    # ------------------------------------------------------------------
    # Topological sort (Kahn's algorithm)
    # ------------------------------------------------------------------

    def _topological_sort(self) -> None:
        """Topologically sort nodes based on edges, detecting cycles."""
        # Build adjacency and in-degree maps
        in_degree: Dict[str, int] = dict.fromkeys(self._instances, 0)
        adjacency: Dict[str, List[str]] = {nid: [] for nid in self._instances}

        for edge in self._raw_edges:
            src = _norm_node_id(edge.get("source", ""))
            tgt = _norm_node_id(edge.get("target", ""))
            if not src or not tgt:
                continue
            if src not in self._instances or tgt not in self._instances:
                continue
            adjacency.setdefault(src, []).append(tgt)
            in_degree[tgt] = in_degree.get(tgt, 0) + 1

        # Kahn's algorithm
        ready: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
        order: List[str] = []

        while ready:
            nid = ready.popleft()
            order.append(nid)
            for neighbor in adjacency.get(nid, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    ready.append(neighbor)

        if len(order) != len(self._instances):
            remaining = set(self._instances) - set(order)
            raise ValueError(f"Workflow contains a cycle. Unresolved nodes: {sorted(remaining)}")

        self._execution_order = order
        logger.info(f"Topological order: {' → '.join(order)}")

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def _execute_all(self) -> None:
        """Execute all nodes in topological order."""
        for nid in self._execution_order:
            await self._execute_node(nid)

    async def _execute_node(self, node_id: str) -> None:
        """Execute a single node and store its result."""
        instance = self._instances.get(node_id)
        if instance is None:
            return

        type_name = type(instance).__name__
        await self._emit(
            "node_start",
            {"node_id": node_id, "node_type": type_name},
        )

        try:
            # Resolve inputs from upstream nodes via edges
            cxt = await self._resolve_inputs(node_id)

            # Apply ctx_override: copy context values into instance fields
            if instance.ctx_override:
                for field_name in instance.model_fields:
                    if field_name in cxt:
                        try:
                            setattr(instance, field_name, cxt[field_name])
                        except Exception as exc:  # noqa: BLE001
                            logger.debug(f"Could not set field {field_name!r} on {type_name!r} from context: {exc!r}")

            # Execute. The node body runs off-loop in a daemon worker thread
            # (its own event loop), so blocking sync I/O (e.g. ReadText on a
            # 20 MB file) never stalls this loop: the await below stays
            # cancellable, and an interrupt is delivered here immediately while
            # the orphaned thread finishes in the background (abandonment, not
            # killing — see _run_node_body). Note: LLM calls (aask) are
            # pyo3-asyncio awaitables that bind to the running loop at await
            # time, so they work inside the thread's own loop; any action that
            # instead captures the main loop's resources would not.
            result = await asyncio.get_running_loop().run_in_executor(
                _NODE_BODY_EXECUTOR, _run_node_body, instance, cxt
            )
            output_key: str = (
                instance.output_key
                or getattr(instance, "output_key", "")
                or instance.model_fields.get("output_key", FieldInfo()).default
                or node_id
            )
            self._context[output_key] = result

            await self._emit(
                "node_done",
                {
                    "node_id": node_id,
                    "node_type": type_name,
                    "output_key": output_key,
                    "output": _preview(result),
                },
            )
            await self._emit(
                "node_output",
                {
                    "node_id": node_id,
                    "node_type": type_name,
                    "output_key": output_key,
                    "output": _preview(result),
                },
            )

        except Exception as exc:
            logger.error(f"Node {node_id} ({type_name}) failed: {exc!r}")
            await self._emit(
                "node_error",
                {
                    "node_id": node_id,
                    "node_type": type_name,
                    "error": str(exc),
                },
            )
            raise

    async def _resolve_inputs(self, node_id: str) -> Dict[str, Any]:
        """Build the context dict for *node_id* by reading upstream outputs."""
        cxt: Dict[str, Any] = {}

        for edge in self._raw_edges:
            tgt = _norm_node_id(edge.get("target", ""))
            if tgt != node_id:
                continue

            src = _norm_node_id(edge.get("source", ""))
            target_handle = edge.get("targetHandle", "")
            source_handle = edge.get("sourceHandle", "")

            if src not in self._instances:
                continue

            src_instance = self._instances[src]
            src_output_key = (
                source_handle
                or src_instance.output_key
                or getattr(src_instance, "output_key", "")
                or src_instance.model_fields.get("output_key", FieldInfo()).default
                or src
            )

            value = self._context.get(src_output_key)
            if value is not None or src_output_key in self._context:
                handle = target_handle or src_output_key
                cxt[handle] = value

        return cxt

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------

    async def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Emit an event through the callback, swallowing callback errors."""
        try:
            await self._event(event_type, payload)
        except Exception:  # noqa: BLE001
            logger.warn(f"Event callback raised for event {event_type!r}; continuing.")

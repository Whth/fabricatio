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
from functools import lru_cache
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Type

from fabricatio_core.journal import logger
from fabricatio_core.models.action import INPUT_KEY, Action
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
# Execution-plan compilation (cached)
# ---------------------------------------------------------------------------
#
# The per-run pipeline — parse nodes/edges, resolve Action classes by name,
# check configurability, topologically sort — is deterministic for a given
# workflow and class universe.  It is compiled once per workflow and cached;
# only Action *instances* are recreated per run (ctx_override and node bodies
# mutate instance state, so instances are never shared).


def _plan_key(wf: Dict[str, Any]) -> str:
    """Canonical JSON of the plan-relevant parts of a workflow.

    ``init_context`` and ``task_input`` do not affect the plan (they are
    seeded into the runtime context per run), so they are excluded.
    """
    return json.dumps(
        {"nodes": wf.get("nodes", []), "edges": wf.get("edges", [])},
        sort_keys=True,
        default=str,
    )


def _registry_version() -> str:
    """Fingerprint of the Action class universe, used to invalidate plans.

    Delegates to the registry's ``registry_version`` (sha1 over the full
    node-type introspection); falls back to ``""`` when unavailable, in which
    case plans are keyed on the workflow alone.
    """
    try:
        from fabricatio_webui.registry import _worker_registry

        return _worker_registry().get("registry_version", "")
    except Exception:  # noqa: BLE001
        return ""


def _find_action_class(type_name: str) -> Optional[Type[Action]]:
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


def _topological_order(instances: Set[str], raw_edges: List[Dict[str, Any]]) -> List[str]:
    """Topologically sort nodes based on edges, detecting cycles (Kahn's)."""
    in_degree: Dict[str, int] = dict.fromkeys(instances, 0)
    adjacency: Dict[str, List[str]] = {nid: [] for nid in instances}

    for edge in raw_edges:
        src = _norm_node_id(edge.get("source", ""))
        tgt = _norm_node_id(edge.get("target", ""))
        if not src or not tgt:
            continue
        if src not in instances or tgt not in instances:
            continue
        adjacency.setdefault(src, []).append(tgt)
        in_degree[tgt] = in_degree.get(tgt, 0) + 1

    ready: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
    order: List[str] = []

    while ready:
        nid = ready.popleft()
        order.append(nid)
        for neighbor in adjacency.get(nid, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                ready.append(neighbor)

    if len(order) != len(instances):
        remaining = sorted(set(instances) - set(order))
        raise ValueError(f"Workflow contains a cycle. Unresolved nodes: {remaining}")

    logger.info(f"Topological order: {' → '.join(order)}")
    return order


@dataclass(frozen=True)
class _NodeSpec:
    """Resolved per-node plan data: class + config.  Instances are per-run."""

    action_class: Type[Action]
    config: Dict[str, Any]
    explicit_ctx_override: Optional[bool]
    instantiable: bool


@dataclass(frozen=True)
class _CompiledPlan:
    """Cached execution plan for one workflow graph."""

    raw_nodes: Dict[str, Dict[str, Any]]
    raw_edges: List[Dict[str, Any]]
    specs: Dict[str, _NodeSpec]
    execution_order: List[str]


@lru_cache(maxsize=128)
def _compile_plan(registry_version: str, plan_key: str) -> _CompiledPlan:
    """Parse + resolve + topo-sort a workflow once, caching the result.

    Also performs a throwaway instantiation per node to record whether the
    config is valid, matching the original per-run behavior where
    uninstantiable nodes are excluded from the graph.  Callers recreate
    instances per run from specs.
    """
    wf = json.loads(plan_key)
    raw_nodes: Dict[str, Dict[str, Any]] = {}
    for node in wf.get("nodes", []):
        nid = _norm_node_id(node.get("id", ""))
        if not nid:
            logger.warn(f"Skipping node without an id: {node!r}")
            continue
        raw_nodes[nid] = dict(node)

    raw_edges: List[Dict[str, Any]] = list(wf.get("edges", []))

    specs: Dict[str, _NodeSpec] = {}
    instantiable: Set[str] = set()
    for nid, node in raw_nodes.items():
        type_name: str = node.get("type", "")
        if not type_name:
            logger.warn(f"Node {nid!r} has no type; skipping.")
            continue

        cls = _find_action_class(type_name)
        if cls is None:
            logger.warn(f"Action class {type_name!r} not found for node {nid!r}; skipping.")
            continue

        config: Dict[str, Any] = dict(node.get("config", {}))
        explicit_ctx_override: Optional[bool] = node.get("ctx_override") if "ctx_override" in node else None

        try:
            cls(**config)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Failed to instantiate {type_name!r} for node {nid!r}: {exc!r}; skipping.")
            instantiable_now = False
        else:
            instantiable_now = True

        specs[nid] = _NodeSpec(cls, config, explicit_ctx_override, instantiable_now)
        if instantiable_now:
            instantiable.add(nid)

    execution_order = _topological_order(instantiable, raw_edges)
    return _CompiledPlan(raw_nodes, raw_edges, specs, execution_order)


# ---------------------------------------------------------------------------
# WorkflowExecutor
# ---------------------------------------------------------------------------


@dataclass
class WorkflowExecutor:
    """Executes a workflow graph described by JSON.

    Parameters:
        workflow_json: the workflow descriptor (``{"nodes": […], "edges":[…]}"``).
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
    _seeded: Dict[str, Any] = field(init=False, default_factory=dict)

    @classmethod
    def new(
        cls,
        workflow_json: Dict[str, Any],
        event_callback: Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]],
        task_input: Any = None,
    ) -> "WorkflowExecutor":
        """Create a new executor from a workflow JSON descriptor.

        ``task_input`` (the per-execution payload from ``ExecutionRequest``) is
        seeded into the execution context: a dict is merged key-by-key, any
        other JSON value is stored under the framework's reserved
        ``INPUT_KEY`` (``"task_input"``). The workflow's ``init_context`` is
        seeded first, then ``task_input`` is overlaid on top — on key
        conflicts ``task_input`` wins, since it is the more specific,
        per-call input. Seeded values are visible to every node and are part
        of the returned result context.
        """
        inst = cls()
        inst._wf = workflow_json
        inst._event = event_callback
        inst._seed_context(task_input)
        return inst

    def _seed_context(self, task_input: Any) -> None:
        """Seed the execution context with ``init_context`` and ``task_input``."""
        init_context = self._wf.get("init_context")
        if isinstance(init_context, dict):
            self._seeded.update(init_context)
        elif init_context:
            logger.warn(f"init_context is not a dict; ignoring: {init_context!r}")

        if isinstance(task_input, dict):
            self._seeded.update(task_input)
        elif task_input is not None:
            self._seeded[INPUT_KEY] = task_input

        self._context.update(self._seeded)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def execute(self) -> Dict[str, Any]:
        """Execute the workflow and return the final context dictionary."""
        await self._emit("execution_start", {"node_count": len(self._wf.get("nodes", []))})

        try:
            plan = _compile_plan(_registry_version(), _plan_key(self._wf))
            self._raw_nodes = plan.raw_nodes
            self._raw_edges = plan.raw_edges
            self._execution_order = plan.execution_order
            self._instantiate_from_plan(plan)
            await self._execute_all()
        except Exception as exc:
            logger.error(f"Workflow execution failed: {exc!r}")
            await self._emit("execution_done", {"status": "error"})
            raise

        await self._emit("execution_done", {"status": "ok"})
        return dict(self._context)

    # ------------------------------------------------------------------
    # Instantiation (per run — instances are never shared between runs)
    # ------------------------------------------------------------------

    def _instantiate_from_plan(self, plan: "_CompiledPlan") -> None:
        """Create fresh Action instances from a compiled plan.

        The plan holds resolved classes and configs, but instances must be
        recreated on every run: ``ctx_override`` and node bodies mutate
        instance fields, so a cached instance would leak state across runs.
        """
        for nid, spec in plan.specs.items():
            if not spec.instantiable:
                continue
            try:
                instance = spec.action_class(**spec.config)
            except Exception as exc:  # noqa: BLE001 — compile-time check passed; guard anyway
                logger.error(
                    f"Failed to instantiate {spec.action_class.__name__!r} for node {nid!r}: {exc!r}; skipping."
                )
                continue
            if spec.explicit_ctx_override is not None:
                instance.ctx_override = spec.explicit_ctx_override
            self._instances[nid] = instance

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

            # Seed values (init_context + task_input) are visible to every
            # node, even without incoming edges (e.g. a Forward node looking
            # up a key from init_context); explicit edge wiring wins on
            # conflicts.
            cxt = {**self._seeded, **cxt}

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
            # Support both camelCase (legacy) and snake_case (current) handle keys.
            target_handle = edge.get("targetHandle", "") or edge.get("target_handle", "")
            source_handle = edge.get("sourceHandle", "") or edge.get("source_handle", "")

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

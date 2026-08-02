"""Role/WorkFlow/Task execution for the fabricatio-webui board editor.

Saved boards are built into fabricatio ``Role`` objects and dispatched onto
the global EMITTER at startup and after every save/delete. Publishing a
``Task`` routes it to every workflow whose subscription pattern matches the
task's namespace — the real fabricatio execution model. Node lifecycle
events stream through instrumented Action instances that wrap each node
body; wired edge values are applied per execution from a task-scoped
output store (instances are shared across tasks by framework design).
"""

import asyncio
import concurrent.futures
import json
import threading
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type

import orjson
from fabricatio_core.journal import logger
from fabricatio_core.models.action import INPUT_KEY, Action, WorkFlow
from fabricatio_core.models.role import Role
from fabricatio_core.models.task import Task
from pydantic.fields import FieldInfo

# Task-scoped storage keys (namespaced away from user keys).
_OUTPUTS_KEY = "__webui_node_outputs__"
_FIELDS_KEY = "__webui_node_fields__"  # {node_id: {field: effective value}}
_EXECUTION_ID_KEY = "__webui_execution_id__"
_ERRORS_KEY = "__webui_errors__"

# Injected by the worker at startup; broadcasts WS JSON to Rust.
_broadcast: Optional[Callable[[str], None]] = None


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


def _registry_version() -> str:
    """Fingerprint of the Action class universe, used to invalidate plans."""
    try:
        from fabricatio_webui.registry import _worker_registry

        return _worker_registry().get("registry_version", "")
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------
# Node-body offloading (interrupt preemption)
# ---------------------------------------------------------------------------


class _NodeBodyExecutor:
    """Runs each node body in a fresh daemon thread.

    ``asyncio.to_thread`` / ``run_in_executor(None, ...)`` would use the loop's
    default ThreadPoolExecutor, whose worker threads are *non-daemon* and are
    joined at interpreter exit. A cancelled node that keeps running in the
    background would therefore block process shutdown until it finishes.
    Daemon threads are never joined, so an orphaned node body simply dies
    with the interpreter.
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


# ---------------------------------------------------------------------------
# Action/plan resolution helpers
# ---------------------------------------------------------------------------


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


def _class_output_key(cls: Type[Action]) -> str:
    """Registry-style output port name for an Action class.

    Mirrors ``registry._extract_output_ports``: ``output_key`` when set,
    else the class name lowercased.
    """
    return (
        getattr(cls, "output_key", "")
        or cls.model_fields.get("output_key", FieldInfo()).default
        or cls.__name__.lower()
    )


def _resolve_output_key(instance: Action, node_id: str) -> str:
    """The context key a node's result is stored under (per-node safe)."""
    return (
        instance.output_key
        or getattr(instance, "output_key", "")
        or instance.model_fields.get("output_key", FieldInfo()).default
        or type(instance).__name__.lower()
        or node_id
    )


# ---------------------------------------------------------------------------
# Execution-plan compilation (cached)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _NodePlan:
    action_class: Type[Action]
    config: Dict[str, Any]
    wired: Tuple[Tuple[str, str, str], ...]  # (source_id, source_handle, target_handle)


@dataclass(frozen=True)
class _WorkflowPlan:
    nodes: Dict[str, _NodePlan]
    order: Tuple[str, ...]
    task_output_key: str
    init_context: Dict[str, Any]


def _workflow_plan_key(wf: Dict[str, Any]) -> str:
    """Canonical JSON of the plan-relevant parts of a workflow."""
    return json.dumps(
        {
            "nodes": wf.get("nodes", []),
            "edges": wf.get("edges", []),
            "init_context": wf.get("init_context", {}),
            "task_output_key": wf.get("task_output_key"),
        },
        sort_keys=True,
        default=str,
    )


@lru_cache(maxsize=128)
def _compile_workflow_plan(registry_version: str, plan_key: str) -> _WorkflowPlan:  # noqa: C901
    """Parse + resolve + topo-sort one workflow graph, caching the result."""
    wf = json.loads(plan_key)

    raw_nodes: Dict[str, Dict[str, Any]] = {}
    for node in wf.get("nodes", []):
        nid = _norm_node_id(node.get("id", ""))
        if not nid:
            logger.warn(f"Skipping node without an id: {node!r}")
            continue
        raw_nodes[nid] = dict(node)

    raw_edges: List[Dict[str, Any]] = list(wf.get("edges", []))

    incoming: Dict[str, List[Tuple[str, str, str]]] = {nid: [] for nid in raw_nodes}
    for edge in raw_edges:
        src = _norm_node_id(edge.get("source", ""))
        tgt = _norm_node_id(edge.get("target", ""))
        if not src or not tgt or tgt not in raw_nodes:
            continue
        source_handle = edge.get("sourceHandle", "") or edge.get("source_handle", "")
        target_handle = edge.get("targetHandle", "") or edge.get("target_handle", "")
        incoming.setdefault(tgt, []).append((src, source_handle, target_handle))

    nodes: Dict[str, _NodePlan] = {}
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
        wired = tuple(incoming.get(nid, []))

        try:
            _instantiate_action(cls, config, wired)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Failed to instantiate {type_name!r} for node {nid!r}: {exc!r}; skipping.")
            continue

        nodes[nid] = _NodePlan(cls, config, wired)
        instantiable.add(nid)

    order = tuple(_topological_order(instantiable, raw_edges))

    default_output_key = ""
    if order:
        default_output_key = _class_output_key(nodes[order[-1]].action_class)

    init_context = wf.get("init_context", {})
    if not isinstance(init_context, dict):
        logger.warn(f"init_context is not a dict; ignoring: {init_context!r}")
        init_context = {}

    task_output_key: str = wf.get("task_output_key") or default_output_key
    return _WorkflowPlan(nodes, order, task_output_key, dict(init_context))


# ---------------------------------------------------------------------------
# Instrumented actions (node events + per-task wired resolution)
# ---------------------------------------------------------------------------


def _wired_value(
    fields_store: Dict[str, Dict[str, Any]],
    outputs: Dict[str, Any],
    node_id: str,
    src_id: str,
    source_handle: str,
    tgt_handle: str,
) -> Tuple[bool, Any]:
    """Resolve one wired edge's runtime value.

    ``source_handle`` prefixed with ``field:`` reads the source node's
    recorded effective field value; anything else reads the node's output.
    Returns ``(found, value)``; missing sources warn and report ``False``.
    """
    if source_handle.startswith("field:"):
        field_name = source_handle[len("field:") :]
        src_fields = fields_store.get(src_id, {})
        if field_name not in src_fields:
            logger.warn(f"Node {node_id}: field {src_id!r}.{field_name!r} not recorded; skipping field {tgt_handle!r}.")
            return False, None
        return True, src_fields[field_name]
    if src_id not in outputs:
        logger.warn(f"Node {node_id}: output of {src_id!r} not available; skipping field {tgt_handle!r}.")
        return False, None
    return True, outputs[src_id]


def _instantiate_action(
    cls: Type[Action],
    config: Dict[str, Any],
    wired: Tuple[Tuple[str, str, str], ...],
) -> Action:
    """Instantiate a node's action, tolerating required fields that wired
    edges supply at runtime.

    Strict construction validates the config.  When it fails solely because
    required fields are missing from the config yet covered by incoming
    edges (their values are setattr'd in ``_execute`` before the body runs),
    fall back to the non-validating ``model_construct`` — re-applying
    ``model_post_init`` — instead of dropping the node from the plan.
    """
    try:
        return cls(**config)
    except Exception:
        required_missing = {
            name for name, field in cls.model_fields.items() if field.is_required() and name not in config
        }
        wired_targets = {tgt for _, _, tgt in wired}
        if required_missing and required_missing <= wired_targets:
            instance = cls.model_construct(**config)
            instance.model_post_init(None)
            return instance
        raise


def _make_instrumented(  # noqa: C901
    real_cls: Type[Action],
    node_id: str,
    wired: Tuple[Tuple[str, str, str], ...],
) -> Type[Action]:
    """Create a per-node Action subclass that emits lifecycle events.

    The subclass is a real subclass of the node's Action class, so the
    framework's ``act``/``serve`` machinery treats it as the node itself.
    Wired edge values resolve from the task-scoped output store at execution
    time (instances are shared across tasks by framework design).
    """
    body = real_cls._execute
    class_name = real_cls.__name__

    class _Instrumented(real_cls):  # type: ignore[misc, valid-type]
        async def _execute(self, *args: Any, **cxt: Any) -> Any:
            task = cxt.get(INPUT_KEY)
            outputs: Dict[str, Any] = {}
            fields_store: Dict[str, Dict[str, Any]] = {}
            execution_id: Optional[str] = None
            if isinstance(task, Task):
                outputs = task.extra_init_context.setdefault(_OUTPUTS_KEY, {})
                fields_store = task.extra_init_context.setdefault(_FIELDS_KEY, {})
                execution_id = task.extra_init_context.get(_EXECUTION_ID_KEY)

            # Wired edge values are explicit field assignments: applied
            # unconditionally (bodies read ``self.<field>``), regardless of
            # ctx_override, and injected into the body context.  A source
            # handle prefixed with "field:" resolves to the source node's
            # recorded effective field value (manual config, its own wired
            # input, or an init_context override) instead of its output.
            for src_id, source_handle, tgt_handle in wired:
                found, value = _wired_value(fields_store, outputs, node_id, src_id, source_handle, tgt_handle)
                if not found:
                    continue
                cxt[tgt_handle] = value
                if tgt_handle in type(self).model_fields:
                    try:
                        setattr(self, tgt_handle, value)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug(f"Could not set wired field {tgt_handle!r} on {class_name!r}: {exc!r}")

            # Record effective field values (after wire-in, before the body)
            # so field-source edges from this node forward what it takes in.
            if isinstance(task, Task):
                fields_store[node_id] = {
                    name: getattr(self, name) for name in type(self).model_fields if hasattr(self, name)
                }

            await _emit(
                execution_id,
                "node_start",
                {"node_id": node_id, "node_type": class_name},
            )

            def run_body() -> Any:
                return asyncio.run(body(self, *args, **cxt))

            try:
                result = await asyncio.get_running_loop().run_in_executor(_NODE_BODY_EXECUTOR, run_body)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Node {node_id} ({class_name}) failed: {exc!r}")
                if isinstance(task, Task):
                    task.extra_init_context.setdefault(_ERRORS_KEY, []).append(str(exc))
                await _emit(
                    execution_id,
                    "node_error",
                    {"node_id": node_id, "node_type": class_name, "error": str(exc)},
                )
                raise

            outputs[node_id] = result
            output_key = _resolve_output_key(self, node_id)
            payload = {
                "node_id": node_id,
                "node_type": class_name,
                "output_key": output_key,
                "output": _preview(result),
            }
            await _emit(execution_id, "node_done", payload)
            await _emit(execution_id, "node_output", payload)
            return result

    _Instrumented.__name__ = class_name
    _Instrumented.__qualname__ = class_name
    return _Instrumented


async def _emit(execution_id: Optional[str], event_type: str, payload: Dict[str, Any]) -> None:
    """Broadcast a WS event through the injected rust_broadcast callable."""
    if _broadcast is None:
        return
    msg: Dict[str, Any] = {"type": event_type, **payload}
    if execution_id is not None:
        msg["execution_id"] = execution_id
    try:
        _broadcast(orjson.dumps(msg).decode())
    except Exception:  # noqa: BLE001
        logger.warn(f"Broadcast failed for {event_type}")


# ---------------------------------------------------------------------------
# WorkFlow / Role construction
# ---------------------------------------------------------------------------


def _subscription_pattern(namespace: str) -> str:
    """Derive the EMITTER subscription pattern from a plain namespace.

    A task with ``send_to = ["write", "book"]`` publishes
    ``write::book::<task_name>::Pending``; the wildcard pattern
    ``write::book::*::Pending`` matches every task in that namespace.
    """
    ns = namespace.strip().strip(":")
    if not ns:
        return ""
    return f"{ns}::*::Pending"


def _workflow_class(output_key: str) -> Type[WorkFlow]:
    """A WorkFlow subclass carrying the task output key (a ClassVar)."""
    return type("WebuiWorkFlow", (WorkFlow,), {"task_output_key": output_key})


def _build_workflow(plan: _WorkflowPlan) -> WorkFlow:
    """Instantiate a WorkFlow from a plan (shared across tasks, per design)."""
    instances: List[Action] = []
    for node_id in plan.order:
        node_plan = plan.nodes[node_id]
        cls = _make_instrumented(node_plan.action_class, node_id, node_plan.wired)
        try:
            instance = _instantiate_action(cls, node_plan.config, node_plan.wired)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"Failed to instantiate {node_plan.action_class.__name__!r} for node {node_id!r}: {exc!r}; skipping."
            )
            continue
        # Empty output_key actions still publish their result under the
        # registry port name (class-lower) so context readers can find it.
        if not instance.output_key:
            instance.output_key = _class_output_key(node_plan.action_class)
        instances.append(instance)

    return _workflow_class(plan.task_output_key)(
        name="webui-workflow",
        steps=instances,
        extra_init_context=dict(plan.init_context),
    )


def _build_role(role_name: str, subscriptions: Dict[str, WorkFlow], description: str = "") -> Role:
    """Create a role and dispatch it onto the EMITTER."""
    return Role.new(subscriptions, name=role_name, description=description).dispatch()


# ---------------------------------------------------------------------------
# Board → roles (the webui's dispatch registry)
# ---------------------------------------------------------------------------


def _load_boards(data_dir: Path) -> List[Dict[str, Any]]:
    """Read + migrate all saved boards from the Rust-persisted store."""
    from fabricatio_webui.registry import migrate_board

    path = Path(data_dir) / "workflows.json"
    try:
        raw = orjson.loads(path.read_bytes())
    except FileNotFoundError:
        return []
    except Exception as exc:  # noqa: BLE001
        logger.warn(f"Failed to read {path}: {exc!r}")
        return []

    boards: List[Dict[str, Any]] = []
    values = raw.values() if isinstance(raw, dict) else []
    for value in values:
        if not isinstance(value, dict):
            continue
        try:
            boards.append(migrate_board(value))
        except Exception as exc:  # noqa: BLE001
            logger.warn(f"Failed to migrate a saved board: {exc!r}")
    return boards


def build_roles_from_boards(boards: List[Dict[str, Any]]) -> List[Role]:
    """Compile every role in *boards* and dispatch it onto the EMITTER."""
    roles: List[Role] = []
    for board in boards:
        for role_json in board.get("roles", []):
            role_name = str(role_json.get("name", "")).strip()
            if not role_name:
                logger.warn("A board contains a role without a name; skipping.")
                continue

            subscriptions: Dict[str, WorkFlow] = {}
            for wf_json in role_json.get("workflows", []):
                try:
                    plan = _compile_workflow_plan(_registry_version(), _workflow_plan_key(wf_json))
                except Exception as exc:  # noqa: BLE001 — e.g. a cycle
                    logger.error(
                        f"Workflow {wf_json.get('name', '?')} in role {role_name!r} failed to compile: {exc!r}"
                    )
                    continue
                pattern = _subscription_pattern(str(wf_json.get("namespace") or wf_json.get("name") or ""))
                if not pattern:
                    logger.warn(
                        f"Workflow {wf_json.get('name', '?')} in role {role_name!r} has no namespace; not subscribable."
                    )
                    continue
                subscriptions[pattern] = _build_workflow(plan)

            if not subscriptions:
                logger.warn(f"Role {role_name!r} has no subscribable workflows; skipping.")
                continue

            try:
                roles.append(_build_role(role_name, subscriptions, str(role_json.get("description", ""))))
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Failed to build role {role_name!r}: {exc!r}")
    return roles


class RoleRegistry:
    """Owns the roles built from saved boards; re-dispatches on change.

    Tracks every role this process has dispatched (module-level, so a fresh
    registry instance — e.g. in tests — still undoes its predecessors).
    """

    def __init__(self, data_dir: Path) -> None:
        """Create the registry reading boards from ``data_dir``."""
        self._data_dir = Path(data_dir)

    def rebuild(self) -> None:
        """Undo-dispatch the current roles and re-dispatch from the store."""
        for role in _DISPATCHED_ROLES:
            try:
                role.undo_dispatch()
            except Exception as exc:  # noqa: BLE001
                logger.warn(f"Failed to undo dispatch of role {role.name!r}: {exc!r}")
        _DISPATCHED_ROLES.clear()
        _DISPATCHED_ROLES.extend(build_roles_from_boards(_load_boards(self._data_dir)))
        logger.info(f"Dispatched {len(_DISPATCHED_ROLES)} role(s) from saved boards.")


_DISPATCHED_ROLES: List[Role] = []

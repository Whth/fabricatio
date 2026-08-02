"""Tests for the role/workflow/task execution machinery."""

import asyncio
from typing import Any

import pytest
from pydantic import Field

from fabricatio_core.models.action import Action, WorkFlow
from fabricatio_core.models.task import Task
from fabricatio_webui.executor import (
    _build_workflow,
    _compile_workflow_plan,
    _subscription_pattern,
    _topological_order,
    _workflow_plan_key,
    build_roles_from_boards,
)


# ── Test action helpers ────────────────────────────────────────────────────────


class EchoStep(Action):
    """Returns its configured value."""

    value: str = "default"
    output_key: str = "echo"

    async def _execute(self, **cxt: Any) -> Any:
        return self.value


class PickStep(Action):
    """Reads a named key from the execution context."""

    key: str = "k"
    output_key: str = "pick"

    async def _execute(self, **cxt: Any) -> Any:
        return cxt.get(self.key)


class StatefulStep(Action):
    """Node that accumulates into its own list field.

    With the real fabricatio stack, workflow instances are shared across
    tasks (a dispatched workflow is a long-lived subscription), so state
    intentionally persists between serves of the same workflow.
    """

    seen: list[str] = Field(default_factory=list)
    output_key: str = "stateful"

    async def _execute(self, **cxt: Any) -> Any:
        self.seen.append("x")
        return list(self.seen)


class TwoFieldStep(Action):
    """Node with two configurable fields; echoes both as a dict."""

    left: str = "L0"
    right: str = "R0"
    output_key: str = "two"

    async def _execute(self, **cxt: Any) -> Any:
        return {"left": self.left, "right": self.right}


class NoKeyStep(Action):
    """Action without an output_key default.

    Its registry port name is the lowercased class name (``nokeystep``), so
    edges must resolve to that key.
    """

    text: str = ""

    async def _execute(self, **cxt: Any) -> Any:
        return self.text


class NullStep(Action):
    """Side-effect-only action: returns nothing."""

    output_key: str = "nulled"

    async def _execute(self, **cxt: Any) -> Any:
        return None


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_plan_cache():
    """Isolate each test with a fresh plan cache."""
    _compile_workflow_plan.cache_clear()
    yield
    _compile_workflow_plan.cache_clear()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _wf(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    init_context: dict[str, Any] | None = None,
    task_output_key: str | None = None,
) -> dict[str, Any]:
    return {
        "nodes": nodes,
        "edges": edges,
        "init_context": init_context or {},
        "task_output_key": task_output_key,
    }


def _node(node_id: str, node_type: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": node_id, "type": node_type, "inputs": {}, "config": config or {}}


def _build(wf: dict[str, Any]) -> WorkFlow:
    """Compile a workflow plan and instantiate it (no EMITTER)."""
    plan = _compile_workflow_plan("test-registry", _workflow_plan_key(wf))
    return _build_workflow(plan)


async def _serve(wf: dict[str, Any], task: Task | None = None) -> Task:
    """Serve a workflow directly with a fresh task; returns the finished task."""
    workflow = _build(wf)
    t = task or Task(name="t", send_to=["test"])
    await workflow.serve(t)
    return t


async def _run(wf: dict[str, Any], task: Task | None = None) -> tuple[Any, Task]:
    """Run a workflow and return ``(output, task)``."""
    t = await _serve(wf, task)
    return await t.get_output(), t


# ── Plan-cache tests ──────────────────────────────────────────────────────────


def test_same_workflow_reuses_cached_plan():
    """Identical workflows compile to the same cached plan object."""
    wf = _wf([_node("n1", "EchoStep", {"value": "a"})], [])
    plan1 = _compile_workflow_plan("v", _workflow_plan_key(wf))
    plan2 = _compile_workflow_plan("v", _workflow_plan_key(wf))
    assert plan1 is plan2  # same plan object — cache hit


def test_different_config_yields_different_plan():
    """Different node configs produce different cached plans."""
    wf_a = _wf([_node("n1", "EchoStep", {"value": "a"})], [])
    wf_b = _wf([_node("n1", "EchoStep", {"value": "b"})], [])
    plan_a = _compile_workflow_plan("v", _workflow_plan_key(wf_a))
    plan_b = _compile_workflow_plan("v", _workflow_plan_key(wf_b))
    assert plan_a is not plan_b


def test_different_class_universe_yields_different_plan():
    """A different registry version invalidates the cache."""
    wf = _wf([_node("n1", "EchoStep")], [])
    plan_v = _compile_workflow_plan("v", _workflow_plan_key(wf))
    plan_w = _compile_workflow_plan("w", _workflow_plan_key(wf))
    assert plan_v is not plan_w


def test_init_context_is_part_of_plan_key():
    """init_context is baked into workflow construction, so it keys the plan."""
    wf_a = _wf([_node("n1", "EchoStep")], [], init_context={"a": 1})
    wf_b = _wf([_node("n1", "EchoStep")], [], init_context={"a": 2})
    plan_a = _compile_workflow_plan("v", _workflow_plan_key(wf_a))
    plan_b = _compile_workflow_plan("v", _workflow_plan_key(wf_b))
    assert plan_a is not plan_b


# ── Execution semantics tests ─────────────────────────────────────────────────


def _echo_pick_wf(
    source_config: dict[str, Any],
    target_config: dict[str, Any],
    source_handle: str = "echo",
) -> dict[str, Any]:
    """a(EchoStep) → b(EchoStep) → c(PickStep key=echo), observing b's value."""
    return _wf(
        [
            _node("a", "EchoStep", source_config),
            _node("b", "EchoStep", target_config),
            _node("c", "PickStep", {"key": "echo"}),
        ],
        [
            {"source": "a", "source_handle": source_handle, "target": "b", "target_handle": "value"},
            {"source": "b", "source_handle": "echo", "target": "c", "target_handle": "observe"},
        ],
    )


@pytest.mark.asyncio
async def test_wired_value_reaches_field_without_ctx_override() -> None:
    """An edge into a config field wins over the constructor default without ctx_override."""
    out, task = await _run(_echo_pick_wf({"value": "upstream"}, {"value": "cfg"}))
    assert task.is_finished()
    # task output key defaults to the last node's key ("pick")
    assert out == "upstream"
    # the shared context saw b's wired value too
    assert task.extra_init_context  # task-scoped store exists


@pytest.mark.asyncio
async def test_multiple_wired_fields_on_one_node() -> None:
    """A node receives values into BOTH config fields via separate edges."""
    wf = _wf(
        [
            _node("a", "EchoStep", {"value": "L1"}),
            _node("b", "EchoStep", {"value": "R1"}),
            _node("t", "TwoFieldStep", {"left": "L0", "right": "R0"}),
            _node("c", "PickStep", {"key": "two"}),
        ],
        [
            {"source": "a", "source_handle": "echo", "target": "t", "target_handle": "left"},
            {"source": "b", "source_handle": "echo", "target": "t", "target_handle": "right"},
            {"source": "t", "source_handle": "two", "target": "c", "target_handle": "observe"},
        ],
    )
    out, _task = await _run(wf)
    assert out == {"left": "L1", "right": "R1"}


@pytest.mark.asyncio
async def test_same_class_sources_do_not_clobber_each_other() -> None:
    """Two same-class sources keep distinct outputs; each edge resolves to its own."""
    wf = _wf(
        [
            _node("a", "EchoStep", {"value": "A"}),
            _node("b", "EchoStep", {"value": "B"}),
            _node("t", "TwoFieldStep"),
            _node("c", "PickStep", {"key": "two"}),
        ],
        [
            {"source": "a", "source_handle": "echo", "target": "t", "target_handle": "left"},
            {"source": "b", "source_handle": "echo", "target": "t", "target_handle": "right"},
            {"source": "t", "source_handle": "two", "target": "c", "target_handle": "observe"},
        ],
    )
    out, _task = await _run(wf)
    assert out == {"left": "A", "right": "B"}


@pytest.mark.asyncio
async def test_one_source_fans_out_to_many_fields() -> None:
    """A single node output can feed multiple fields of one target."""
    wf = _wf(
        [
            _node("a", "EchoStep", {"value": "x"}),
            _node("t", "TwoFieldStep"),
            _node("c", "PickStep", {"key": "two"}),
        ],
        [
            {"source": "a", "source_handle": "echo", "target": "t", "target_handle": "left"},
            {"source": "a", "source_handle": "echo", "target": "t", "target_handle": "right"},
            {"source": "t", "source_handle": "two", "target": "c", "target_handle": "observe"},
        ],
    )
    out, _task = await _run(wf)
    assert out == {"left": "x", "right": "x"}


@pytest.mark.asyncio
async def test_empty_output_key_edges_resolve_by_class_name() -> None:
    """Nodes without an output_key default resolve edges via the class-name port key."""
    wf = _wf(
        [
            _node("n1", "NoKeyStep", {"text": "hi"}),
            _node("b", "EchoStep", {"value": "default"}),
            _node("c", "PickStep", {"key": "nokeystep"}),
        ],
        [
            {"source": "n1", "source_handle": "nokeystep", "target": "b", "target_handle": "value"},
            {"source": "b", "source_handle": "echo", "target": "c", "target_handle": "observe"},
        ],
    )
    out, _task = await _run(wf)
    assert out == "hi"


@pytest.mark.asyncio
async def test_context_reader_sees_upstream_outputs_without_field_wiring() -> None:
    """Key-reading bodies see earlier outputs via the accumulated context."""
    wf = _wf(
        [
            _node("a", "EchoStep", {"value": "hello"}),
            _node("b", "PickStep", {"key": "echo"}),
        ],
        [{"source": "a", "source_handle": "echo", "target": "b", "target_handle": "observe"}],
    )
    out, _task = await _run(wf)
    assert out == "hello"


@pytest.mark.asyncio
async def test_task_seeded_at_input_key() -> None:
    """The Task object is seeded at the reserved task_input key."""
    wf = _wf([_node("b", "PickStep", {"key": "task_input"})], [])
    out, task = await _run(wf)
    assert out is task


@pytest.mark.asyncio
async def test_null_output_is_a_valid_task_result() -> None:
    """A side-effect-only workflow finishes with a None output, not an error."""
    wf = _wf([_node("n1", "NullStep")], [])
    out, task = await _run(wf)
    assert task.is_finished()
    assert out is None


@pytest.mark.asyncio
async def test_explicit_task_output_key() -> None:
    """task_output_key selects which context key becomes the task output."""
    wf = _wf(
        [_node("a", "EchoStep", {"value": "hello"})],
        [],
        task_output_key="echo",
    )
    out, task = await _run(wf)
    assert task.is_finished()
    assert out == "hello"


@pytest.mark.asyncio
async def test_init_context_seeds_the_shared_context() -> None:
    """init_context values are visible to every node."""
    wf = _wf(
        [_node("b", "PickStep", {"key": "prefix"})],
        [],
        init_context={"prefix": "hello"},
    )
    out, _task = await _run(wf)
    assert out == "hello"


@pytest.mark.asyncio
async def test_shared_instances_persist_state_across_serves() -> None:
    """A dispatched workflow is a long-lived subscription: instances are shared."""
    wf = _wf([_node("n1", "StatefulStep")], [])
    workflow = _build(wf)
    t1 = Task(name="t1", send_to=["test"])
    await workflow.serve(t1)
    out1 = await t1.get_output()
    t2 = Task(name="t2", send_to=["test"])
    await workflow.serve(t2)
    out2 = await t2.get_output()
    assert out1 == ["x"]
    assert out2 == ["x", "x"]


@pytest.mark.asyncio
async def test_edge_to_missing_output_is_skipped_with_warning(capfd: pytest.CaptureFixture[str]) -> None:
    """An edge whose source never produced a value warns instead of crashing."""
    wf = _wf(
        [
            _node("b", "EchoStep", {"value": "default"}),
            _node("c", "PickStep", {"key": "echo"}),
        ],
        [
            {"source": "ghost", "source_handle": "echo", "target": "b", "target_handle": "value"},
            {"source": "b", "source_handle": "echo", "target": "c", "target_handle": "observe"},
        ],
    )
    out, _task = await _run(wf)
    assert out == "default"
    assert "not available" in capfd.readouterr().err


@pytest.mark.asyncio
async def test_unknown_node_type_is_skipped_without_crash() -> None:
    """A node whose type has no matching Action class is skipped."""
    wf = _wf([_node("n1", "NoSuchStepEver")], [])
    out, task = await _run(wf)
    assert task.is_finished()
    assert out is None


@pytest.mark.asyncio
async def test_cyclic_workflow_raises_valueerror() -> None:
    """A workflow with a cycle raises ValueError with the cycle nodes in the message."""
    wf = _wf(
        [_node("a", "EchoStep"), _node("b", "EchoStep")],
        [
            {"source": "a", "source_handle": "echo", "target": "b", "target_handle": "value"},
            {"source": "b", "source_handle": "echo", "target": "a", "target_handle": "value"},
        ],
    )
    with pytest.raises(ValueError, match="cycle"):
        _build(wf)


# ── Subscription pattern tests ────────────────────────────────────────────────


def test_subscription_pattern_derived_from_namespace():
    assert _subscription_pattern("write::book") == "write::book::*::Pending"
    assert _subscription_pattern("write") == "write::*::Pending"


def test_subscription_pattern_empty_namespace():
    assert _subscription_pattern("") == ""
    assert _subscription_pattern("  :: ") == ""


# ── EMITTER integration tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_role_dispatch_serves_task_by_namespace() -> None:
    """A dispatched role's workflow serves a published task on its namespace."""
    board = {
        "format_version": 2,
        "name": "b1",
        "roles": [
            {
                "name": "writer-role",
                "description": "",
                "workflows": [
                    {
                        "name": "write-book",
                        "namespace": "write::book",
                        "nodes": [_node("a", "EchoStep", {"value": "story"})],
                        "edges": [],
                        "init_context": {},
                        "task_output_key": "echo",
                    }
                ],
            }
        ],
        "actions": [],
    }
    roles = build_roles_from_boards([board])
    assert len(roles) == 1
    try:
        task = Task(name="t1", send_to=["write", "book"])
        task.publish()
        out = await asyncio.wait_for(task.get_output(), timeout=5)
        assert task.is_finished()
        assert out == "story"
    finally:
        for role in roles:
            role.undo_dispatch()


@pytest.mark.asyncio
async def test_unmatched_namespace_leaves_task_unserved() -> None:
    """A task published on an unknown namespace is never served."""
    board = {
        "format_version": 2,
        "name": "b1",
        "roles": [
            {
                "name": "reader-role",
                "workflows": [
                    {
                        "name": "read-x",
                        "namespace": "read::x",
                        "nodes": [_node("a", "EchoStep", {"value": "v"})],
                        "edges": [],
                        "task_output_key": "echo",
                    }
                ],
            }
        ],
        "actions": [],
    }
    roles = build_roles_from_boards([board])
    try:
        task = Task(name="t2", send_to=["nowhere"])
        task.publish()
        await asyncio.sleep(0.3)
        # No handler matched: nothing wrote to the task's output queue.
        assert task._output.empty()
    finally:
        for role in roles:
            role.undo_dispatch()


# ── Topological-order unit tests ───────────────────────────────────────────────


def test_topo_single_node():
    order = _topological_order({"n1"}, [])
    assert order == ["n1"]


def test_topo_two_independent_nodes():
    order = _topological_order({"a", "b"}, [])
    assert set(order) == {"a", "b"}


def test_topo_linear_chain():
    edges = [
        {"source": "a", "target": "b"},
        {"source": "b", "target": "c"},
    ]
    order = _topological_order({"a", "b", "c"}, edges)
    assert order.index("a") < order.index("b") < order.index("c")


def test_topo_diamond():
    edges = [
        {"source": "a", "target": "b"},
        {"source": "a", "target": "c"},
        {"source": "b", "target": "d"},
        {"source": "c", "target": "d"},
    ]
    order = _topological_order({"a", "b", "c", "d"}, edges)
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


def test_topo_skips_edges_to_unknown_nodes() -> None:
    """Edges whose source/target is not in the instance set are ignored."""
    edges = [
        {"source": "a", "target": "ghost"},
        {"source": "ghost", "target": "b"},
    ]
    order = _topological_order({"a", "b"}, edges)
    assert set(order) == {"a", "b"}


def test_topo_cycle_raises():
    edges = [
        {"source": "a", "target": "b"},
        {"source": "b", "target": "a"},
    ]
    with pytest.raises(ValueError, match="cycle"):
        _topological_order({"a", "b"}, edges)

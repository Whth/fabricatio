"""Tests for the workflow executor's cached execution-plan compilation."""

import pytest
from pydantic import Field
from typing import Any

from fabricatio_core.models.action import Action
from fabricatio_webui.executor import (
    WorkflowExecutor,
    _compile_plan,
    _plan_key,
    _topological_order,
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
    """Node that mutates its own list field on each execution.

    Guards against instance-sharing between runs: each fresh execution appends
    one element, so a shared instance would accumulate across runs.
    """

    seen: list[str] = Field(default_factory=list)
    output_key: str = "stateful"

    async def _execute(self, **cxt: Any) -> Any:
        self.seen.append("x")
        return list(self.seen)


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_plan_cache():
    """Isolate each test with a fresh plan cache."""
    _compile_plan.cache_clear()
    yield
    _compile_plan.cache_clear()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _wf(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    init_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "nodes": nodes,
        "edges": edges,
        "init_context": init_context or {},
    }


def _node(node_id: str, node_type: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": node_id, "type": node_type, "inputs": {}, "config": config or {}}


async def _run(wf: dict[str, Any], task_input: Any = None) -> dict[str, Any]:
    """Run a workflow and return the result context."""

    async def cb(_event_type: str, _payload: dict[str, Any]) -> None:
        pass

    executor = WorkflowExecutor.new(wf, cb, task_input=task_input)
    return await executor.execute()


# ── Plan-cache tests ──────────────────────────────────────────────────────────


def test_same_workflow_reuses_cached_plan():
    """Identical workflows compile to the same cached plan object."""
    wf1 = _wf([_node("n1", "EchoStep", {"value": "a"})], [])
    wf2 = _wf([_node("n1", "EchoStep", {"value": "a"})], [])
    key1 = _plan_key(wf1)
    key2 = _plan_key(wf2)
    assert key1 == key2

    plan1 = _compile_plan("v", key1)
    plan2 = _compile_plan("v", key2)
    assert plan1 is plan2  # same plan object — cache hit


def test_different_config_yields_different_plan():
    """Different node configs produce different cached plans."""
    wf_a = _wf([_node("n1", "EchoStep", {"value": "a"})], [])
    wf_b = _wf([_node("n1", "EchoStep", {"value": "b"})], [])
    plan_a = _compile_plan("v", _plan_key(wf_a))
    plan_b = _compile_plan("v", _plan_key(wf_b))
    assert plan_a is not plan_b


def test_different_class_universe_yields_different_plan():
    """A different registry version invalidates the cache."""
    wf = _wf([_node("n1", "EchoStep")], [])
    plan_v = _compile_plan("v", _plan_key(wf))
    plan_w = _compile_plan("w", _plan_key(wf))
    assert plan_v is not plan_w


def test_init_context_not_part_of_plan_key():
    """init_context changes do not affect the plan key, so they don't create new cached plans."""
    wf_a = _wf([_node("n1", "EchoStep")], [], init_context={"x": 1})
    wf_b = _wf([_node("n1", "EchoStep")], [], init_context={"x": 2})
    assert _plan_key(wf_a) == _plan_key(wf_b)
    # And the plans themselves are identical
    plan_a = _compile_plan("v", _plan_key(wf_a))
    plan_b = _compile_plan("v", _plan_key(wf_b))
    assert plan_a is plan_b


# ── Execution semantics tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_repeated_execution_is_isolated_and_deterministic():
    """Two runs of the same workflow produce identical results; no state leaks."""
    wf = _wf(
        [
            _node("a", "EchoStep", {"value": "first"}),
            _node("b", "PickStep", {"key": "k"}),
        ],
        [
            {
                "source": "a",
                "source_handle": "echo",
                "target": "b",
                "target_handle": "k",
            }
        ],
    )
    r1 = await _run(wf)
    r2 = await _run(wf)
    assert r1 == r2 == {"echo": "first", "pick": "first"}


@pytest.mark.asyncio
async def test_stateful_node_isolated_per_run():
    """A node that mutates self does not accumulate state across runs."""
    wf = _wf([_node("n1", "StatefulStep")], [])
    r1 = await _run(wf)
    r2 = await _run(wf)
    # Each fresh run starts with an empty list → one "x"
    assert r1["stateful"] == ["x"]
    assert r2["stateful"] == ["x"]
    # If instances were shared, r2 would be ["x", "x"]
    assert r1 == r2


@pytest.mark.asyncio
async def test_cyclic_workflow_raises_valueerror():
    """A workflow with a cycle raises ValueError with the cycle nodes in the message."""
    wf = _wf(
        [_node("a", "EchoStep"), _node("b", "EchoStep")],
        [
            {"source": "a", "source_handle": "echo", "target": "b", "target_handle": "v"},
            {"source": "b", "source_handle": "echo", "target": "a", "target_handle": "v"},
        ],
    )
    with pytest.raises(ValueError, match="cycle"):
        await _run(wf)


@pytest.mark.asyncio
async def test_unknown_node_type_is_skipped_without_crash():
    """A node whose type has no matching Action class is skipped; no exception propagates."""
    wf = _wf([_node("n1", "NoSuchStepEver")], [])
    result = await _run(wf)
    assert result == {}


@pytest.mark.asyncio
async def test_task_input_seeds_context():
    """task_input (dict) overlays init_context and is visible in node results."""
    wf = _wf(
        [_node("n1", "EchoStep", {"value": "cfg"})],
        [],
        init_context={"prefix": "hello"},
    )
    result = await _run(wf, task_input={"prefix": "hi"})
    assert result["prefix"] == "hi"  # task_input wins over init_context
    assert result["echo"] == "cfg"


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


def test_topo_skips_edges_to_unknown_nodes():
    """Edges whose source/target is not in the instance set are ignored."""
    edges = [
        {"source": "a", "target": "ghost"},
        {"source": "a", "target": "b"},
    ]
    order = _topological_order({"a", "b"}, edges)
    assert order == ["a", "b"]


def test_topo_cycle_raises():
    edges = [
        {"source": "a", "target": "b"},
        {"source": "b", "target": "a"},
    ]
    with pytest.raises(ValueError, match="cycle"):
        _topological_order({"a", "b"}, edges)

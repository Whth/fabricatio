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


# ── Field-wiring tests ────────────────────────────────────────────────────────


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
            {"source": "b", "source_handle": "echo", "target": "c", "target_handle": "echo"},
        ],
    )


@pytest.mark.asyncio
async def test_wired_value_reaches_field_without_ctx_override() -> None:
    """An edge into a config field wins over the constructor default without ctx_override."""
    wf = _echo_pick_wf({"value": "upstream"}, {"value": "cfg"})
    result = await _run(wf)
    # b's body returned a's value: the wired field won over its config.
    assert result["pick"] == "upstream"
    assert result["echo"] == "upstream"


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
            {"source": "t", "source_handle": "two", "target": "c", "target_handle": "two"},
        ],
    )
    result = await _run(wf)
    assert result["pick"] == {"left": "L1", "right": "R1"}


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
            {"source": "t", "source_handle": "two", "target": "c", "target_handle": "two"},
        ],
    )
    result = await _run(wf)
    # Without per-node outputs both edges would resolve to whichever EchoStep
    # ran last and both fields would read the same value.
    assert result["pick"] == {"left": "A", "right": "B"}


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
            {"source": "t", "source_handle": "two", "target": "c", "target_handle": "two"},
        ],
    )
    result = await _run(wf)
    assert result["pick"] == {"left": "x", "right": "x"}


@pytest.mark.asyncio
async def test_empty_output_key_edges_resolve_by_class_name() -> None:
    """Nodes without an output_key default resolve edges via the lowercased class-name port key."""
    wf = _wf(
        [
            _node("n1", "NoKeyStep", {"text": "hi"}),
            _node("b", "EchoStep", {"value": "default"}),
            _node("c", "PickStep", {"key": "echo"}),
        ],
        [
            {"source": "n1", "source_handle": "nokeystep", "target": "b", "target_handle": "value"},
            {"source": "b", "source_handle": "echo", "target": "c", "target_handle": "echo"},
        ],
    )
    result = await _run(wf)
    assert result["nokeystep"] == "hi"  # stored under the class-name port key
    assert result["pick"] == "hi"  # wired through to b


@pytest.mark.asyncio
async def test_context_reader_sees_upstream_outputs_without_field_wiring() -> None:
    """Key-reading bodies see earlier outputs via the accumulated context.

    Forward/Gather/DumpText-style bodies read ``cxt.get(key)``; the executor
    must pass the accumulated context like fabricatio's ``WorkFlow.act``.
    """
    wf = _wf(
        [
            _node("a", "EchoStep", {"value": "hello"}),
            _node("b", "PickStep", {"key": "echo"}),
        ],
        # edge only forces ordering; the handle is not a PickStep field, so the
        # value is not setattr'd — b must read it from the shared context
        [{"source": "a", "source_handle": "echo", "target": "b", "target_handle": "observe"}],
    )
    result = await _run(wf)
    assert result["pick"] == "hello"


@pytest.mark.asyncio
async def test_edge_to_missing_output_is_skipped_with_warning(capfd: pytest.CaptureFixture[str]) -> None:
    """An edge whose source never produced a value warns instead of crashing."""
    wf = _wf(
        [
            _node("a", "EchoStep", {"value": "x"}),
            _node("b", "EchoStep", {"value": "default"}),
            _node("c", "PickStep", {"key": "echo"}),
        ],
        [
            {"source": "ghost", "source_handle": "echo", "target": "b", "target_handle": "value"},
            {"source": "b", "source_handle": "echo", "target": "c", "target_handle": "echo"},
        ],
    )
    result = await _run(wf)
    assert result["pick"] == "default"
    assert "no runnable instance" in capfd.readouterr().err


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

"""Tests for the workflow worker loop (task-dispatch model)."""

import asyncio
import json
import time
from typing import Any, Dict, List

import pytest

from fabricatio_core.models.action import Action
from fabricatio_webui.worker import WorkflowWorker


class FakeStep(Action):
    """Test action that records its inputs and returns them."""

    value: str = "default"
    output_key: str = "fake"

    async def _execute(self, **cxt: Any) -> Any:
        return self.value


class HugeListStep(Action):
    """Test action that returns a large non-string result."""

    output_key: str = "huge"

    async def _execute(self, **cxt: Any) -> Any:
        return list(range(30_000))


class SlowStep(Action):
    """Test action that blocks until cancelled."""

    output_key: str = "slow_result"

    async def _execute(self, **cxt: Any) -> Any:
        await asyncio.sleep(3600)
        return {"done": True}


class BlockingStep(Action):
    """Test action whose body does blocking sync work (never yields)."""

    output_key: str = "blocking_result"
    block_seconds: float = 5.0

    async def _execute(self, **cxt: Any) -> Any:
        time.sleep(self.block_seconds)  # noqa: ASYNC251 — deliberate blocking work for preemption tests
        return {"done": True}


class ContextReadStep(Action):
    """Test action that looks up named keys in its execution context."""

    output_key: str = "ctx_read"
    keys: str = ""

    async def _execute(self, **cxt: Any) -> Any:
        wanted = [k.strip() for k in self.keys.split(",") if k.strip()]
        return {k: cxt.get(k) for k in wanted}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _workflow_json(node_id: str, node_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": "wf",
        "namespace": "test",
        "task_output_key": None,
        "nodes": [{"id": node_id, "type": node_type, "inputs": {}, "config": config}],
        "edges": [],
        "init_context": {},
    }


def _board_json(role_name: str, workflows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "format_version": 2,
        "name": role_name,
        "roles": [{"name": role_name, "description": "", "workflows": workflows}],
        "actions": [],
    }


def _write_boards(tmp_path, boards: Dict[str, Dict[str, Any]]) -> None:
    (tmp_path / "workflows.json").write_text(json.dumps(boards), encoding="utf-8")


class Collector:
    """Collects broadcast messages for assertions."""

    def __init__(self) -> None:
        """Create an empty collector."""
        self.messages: List[Dict[str, Any]] = []

    def broadcast(self, raw: str) -> None:
        """Record one broadcast WS frame."""
        self.messages.append(json.loads(raw))

    def by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """Return all messages of one event type."""
        return [m for m in self.messages if m.get("type") == event_type]


async def _run_worker(worker: WorkflowWorker) -> "asyncio.Task[None]":
    task = asyncio.create_task(worker.run())
    await asyncio.sleep(0)  # let the loop start
    return task


async def _wait_for(
    collector: Collector,
    event_type: str,
    timeout: float = 10.0,
    match: Any = None,
) -> Dict[str, Any]:
    """Poll for a message of a type (optionally matching a predicate)."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        msgs = collector.by_type(event_type)
        if msgs:
            latest = msgs[-1]
            if match is None or match(latest):
                return latest
        await asyncio.sleep(0.02)
    raise AssertionError(f"no {event_type} message within {timeout}s; got {collector.messages}")


def _task_json(**overrides: Any) -> str:
    payload = {"name": "t", "send_to": ["test"], **overrides}
    return json.dumps(payload)


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_worker_emits_full_event_sequence(tmp_path: Any) -> None:
    """A successful run broadcasts the full lifecycle event sequence."""
    _write_boards(tmp_path, {"b1": _board_json("r1", [_workflow_json("n1", "FakeStep", {"value": "hello"})])})
    collector = Collector()
    worker = WorkflowWorker(collector.broadcast, tmp_path)
    loop_task = await _run_worker(worker)
    try:
        worker.submit("e1", _task_json())
        start = await _wait_for(collector, "execution_start")
        assert start["execution_id"] == "e1"
        await _wait_for(collector, "node_start")
        await _wait_for(collector, "node_done")
        node_output = await _wait_for(collector, "node_output")
        assert "hello" in str(node_output["output"])
        done = await _wait_for(collector, "execution_done")
        assert done["cancelled"] is False
        assert done["result"] == "hello"
        assert done["error"] is None
    finally:
        loop_task.cancel()


@pytest.mark.asyncio
async def test_interrupt_cancels_running_execution(tmp_path: Any) -> None:
    """Cancelling the current task broadcasts execution_done(cancelled=true)."""
    _write_boards(tmp_path, {"b1": _board_json("r1", [_workflow_json("n1", "SlowStep", {})])})
    collector = Collector()
    worker = WorkflowWorker(collector.broadcast, tmp_path)
    loop_task = await _run_worker(worker)
    try:
        worker.submit("e2", _task_json())
        await _wait_for(collector, "node_start")
        assert worker.cancel_current() is True
        done = await _wait_for(collector, "execution_done")
        assert done["cancelled"] is True
        assert done["result"] is None
    finally:
        loop_task.cancel()


@pytest.mark.asyncio
async def test_interrupt_preempts_blocking_node(tmp_path: Any) -> None:
    """A node doing blocking sync work is preempted by cancel; the loop moves on."""
    _write_boards(tmp_path, {"b1": _board_json("r1", [_workflow_json("n1", "BlockingStep", {"block_seconds": 5.0})])})
    collector = Collector()
    worker = WorkflowWorker(collector.broadcast, tmp_path)
    loop_task = await _run_worker(worker)
    try:
        worker.submit("b1", _task_json())
        await _wait_for(collector, "node_start")
        assert worker.cancel_current() is True
        done = await _wait_for(collector, "execution_done", timeout=8)
        assert done["cancelled"] is True

        # The queue moves on to the next execution while the orphaned thread finishes.
        _write_boards(
            tmp_path,
            {
                "b1": _board_json("r1", [_workflow_json("n1", "FakeStep", {"value": "ok"})]),
                "b2": _board_json("r2", [_workflow_json("n2", "FakeStep", {"value": "ok"})]),
            },
        )
        worker.rebuild_roles()
        await asyncio.sleep(0.1)
        worker.submit("b2", json.dumps({"name": "t", "send_to": ["test"]}))
        done2 = await _wait_for(collector, "execution_done", timeout=8, match=lambda m: m.get("execution_id") == "b2")
        assert done2["result"] == "ok"
        history = json.loads(worker.history_snapshot())
        assert any(h["execution_id"] == "b2" and h["state"] == "completed" for h in history)
    finally:
        loop_task.cancel()


@pytest.mark.asyncio
async def test_blocking_node_completes_normally(tmp_path: Any) -> None:
    """A short blocking node without interrupt still completes with its result."""
    _write_boards(tmp_path, {"b1": _board_json("r1", [_workflow_json("n1", "BlockingStep", {"block_seconds": 0.3})])})
    collector = Collector()
    worker = WorkflowWorker(collector.broadcast, tmp_path)
    loop_task = await _run_worker(worker)
    try:
        worker.submit("e4", _task_json())
        done = await _wait_for(collector, "execution_done", timeout=8)
        assert done["cancelled"] is False
        assert done["result"] == {"done": True}
        assert done["error"] is None
    finally:
        loop_task.cancel()


@pytest.mark.asyncio
async def test_malformed_task_yields_error_without_killing_worker(tmp_path: Any) -> None:
    """A malformed submission fails one execution without stopping the loop."""
    _write_boards(tmp_path, {"b1": _board_json("r1", [_workflow_json("n1", "FakeStep", {})])})
    collector = Collector()
    worker = WorkflowWorker(collector.broadcast, tmp_path)
    loop_task = await _run_worker(worker)
    try:
        worker.submit("e5", "not-json{{{")
        done = await _wait_for(collector, "execution_done")
        assert done["error"] is not None
        # The worker still processes the next submission.
        worker.submit("e6", _task_json())
        done2 = await _wait_for(collector, "execution_done", match=lambda m: m.get("execution_id") == "e6")
        assert done2["error"] is None
    finally:
        loop_task.cancel()


@pytest.mark.asyncio
async def test_huge_result_is_truncated_in_done_and_history(tmp_path: Any) -> None:
    """Oversized results are preview-truncated in both broadcast and history."""
    _write_boards(tmp_path, {"b1": _board_json("r1", [_workflow_json("n1", "HugeListStep", {})])})
    collector = Collector()
    worker = WorkflowWorker(collector.broadcast, tmp_path)
    loop_task = await _run_worker(worker)
    try:
        worker.submit("e7", _task_json())
        done = await _wait_for(collector, "execution_done")
        raw = json.dumps(done)
        assert "[truncated" in raw
        history = json.loads(worker.history_snapshot())
        assert raw not in json.dumps(history)
        assert any("[truncated" in json.dumps(h) for h in history)
    finally:
        loop_task.cancel()


@pytest.mark.asyncio
async def test_history_snapshot_contains_finished_execution(tmp_path: Any) -> None:
    """Finished executions are recorded and visible via history_snapshot."""
    _write_boards(tmp_path, {"b1": _board_json("r1", [_workflow_json("n1", "FakeStep", {"value": "v"})])})
    collector = Collector()
    worker = WorkflowWorker(collector.broadcast, tmp_path)
    loop_task = await _run_worker(worker)
    try:
        worker.submit("e8", _task_json())
        await _wait_for(collector, "execution_done")
        history = json.loads(worker.history_snapshot())
        assert any(h["execution_id"] == "e8" and h["state"] == "completed" for h in history)
        assert any(h["task_name"] == "t" and h["namespace"] == "test" for h in history)
    finally:
        loop_task.cancel()


@pytest.mark.asyncio
async def test_extra_init_context_seeds_execution_context(tmp_path: Any) -> None:
    """extra_init_context from the task payload resolves inside node executions."""
    _write_boards(
        tmp_path,
        {"b1": _board_json("r1", [_workflow_json("n1", "ContextReadStep", {"keys": "user,prefix"})])},
    )
    collector = Collector()
    worker = WorkflowWorker(collector.broadcast, tmp_path)
    loop_task = await _run_worker(worker)
    try:
        worker.submit(
            "e9",
            json.dumps(
                {
                    "name": "t",
                    "send_to": ["test"],
                    "extra_init_context": {"user": "task-user", "prefix": "hello"},
                }
            ),
        )
        done = await _wait_for(collector, "execution_done")
        assert done["result"] == {"user": "task-user", "prefix": "hello"}
    finally:
        loop_task.cancel()


@pytest.mark.asyncio
async def test_no_matching_namespace_fails_fast(tmp_path: Any) -> None:
    """A task on an unknown namespace errors instead of hanging forever."""
    _write_boards(tmp_path, {"b1": _board_json("r1", [_workflow_json("n1", "FakeStep", {})])})
    collector = Collector()
    worker = WorkflowWorker(collector.broadcast, tmp_path)
    loop_task = await _run_worker(worker)
    try:
        worker.submit("e10", json.dumps({"name": "t", "send_to": ["nowhere"]}))
        done = await _wait_for(collector, "execution_done", timeout=8)
        assert done["cancelled"] is False
        assert "No dispatched workflow matches" in (done.get("error") or "")
    finally:
        loop_task.cancel()


@pytest.mark.asyncio
async def test_rebuild_roles_dispatches_new_boards(tmp_path: Any) -> None:
    """Saving a new board and rebuilding dispatches its roles."""
    _write_boards(tmp_path, {"b1": _board_json("r1", [_workflow_json("n1", "FakeStep", {"value": "first"})])})
    collector = Collector()
    worker = WorkflowWorker(collector.broadcast, tmp_path)
    loop_task = await _run_worker(worker)
    try:
        worker.submit("e11", _task_json())
        done = await _wait_for(collector, "execution_done")
        assert done["result"] == "first"

        # A second board with a new namespace becomes dispatchable after rebuild.
        new_board = _board_json("r2", [_workflow_json("n2", "FakeStep", {"value": "second"})])
        new_board["roles"][0]["workflows"][0]["namespace"] = "other"
        _write_boards(
            tmp_path,
            {"b1": _board_json("r1", [_workflow_json("n1", "FakeStep", {"value": "first"})]), "b2": new_board},
        )
        worker.rebuild_roles()
        await asyncio.sleep(0.1)
        worker.submit("e12", json.dumps({"name": "t", "send_to": ["other"]}))
        done2 = await _wait_for(collector, "execution_done", timeout=8, match=lambda m: m.get("execution_id") == "e12")
        assert done2["result"] == "second"
    finally:
        loop_task.cancel()

"""Tests for the workflow worker loop."""

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
    output_key: str = "fake_result"

    async def _execute(self, **cxt: Any) -> Any:
        return self.value


class HugeListStep(Action):
    """Test action that returns a large non-string result."""

    output_key: str = "big_list"

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
    """Test action that looks up named keys in its execution context.

    Mirrors how ``Forward`` reads a value: ``cxt.get(self.original)`` where
    ``cxt`` is the per-node context dict passed to ``_execute``.
    """

    output_key: str = "ctx_read"
    keys: str = ""

    async def _execute(self, **cxt: Any) -> Any:
        wanted = [k.strip() for k in self.keys.split(",") if k.strip()]
        return {k: cxt.get(k) for k in wanted}


def _wf(node_id: str, node_type: str, config: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "nodes": [{"id": node_id, "type": node_type, "inputs": {}, "config": config}],
            "edges": [],
        }
    )


async def _run_worker(worker: WorkflowWorker) -> "asyncio.Task[None]":
    task = asyncio.create_task(worker.run())
    await asyncio.sleep(0)  # let the loop start
    return task


@pytest.mark.asyncio
async def test_worker_emits_full_event_sequence() -> None:
    """A successful run broadcasts the full lifecycle event sequence."""
    events: List[Dict[str, Any]] = []

    def broadcast(payload: str) -> None:
        events.append(json.loads(payload))

    worker = WorkflowWorker(broadcast)
    loop_task = await _run_worker(worker)

    worker.submit("e1", _wf("n1", "FakeStep", {"value": "hello"}), "null")
    await asyncio.sleep(0.05)
    loop_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await loop_task

    types = [e["type"] for e in events]
    assert types == [
        "status",
        "execution_start",
        "node_start",
        "node_done",
        "node_output",
        "execution_done",
        "status",  # trailing queue-depth update from the run-loop finally
    ]
    done = next(e for e in events if e["type"] == "execution_done")
    assert done["execution_id"] == "e1"
    assert done["cancelled"] is False
    assert done["error"] is None
    node_output = next(e for e in events if e["type"] == "node_output")
    assert node_output["node_id"] == "n1"
    assert "hello" in str(node_output["data"])


@pytest.mark.asyncio
async def test_interrupt_cancels_running_execution() -> None:
    """Cancelling the current task broadcasts execution_done(cancelled=true)."""
    events: List[Dict[str, Any]] = []

    def broadcast(payload: str) -> None:
        events.append(json.loads(payload))

    worker = WorkflowWorker(broadcast)
    loop_task = await _run_worker(worker)

    worker.submit("e2", _wf("n1", "SlowStep", {}), "null")
    await asyncio.sleep(0.05)
    assert worker.cancel_current() is True
    await asyncio.sleep(0.05)
    loop_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await loop_task

    done = next(e for e in events if e["type"] == "execution_done")
    assert done["execution_id"] == "e2"
    assert done["cancelled"] is True


@pytest.mark.asyncio
async def test_interrupt_preempts_blocking_node() -> None:
    """A node doing blocking sync work is preempted by cancel; the loop moves on."""
    events: List[Dict[str, Any]] = []

    def broadcast(payload: str) -> None:
        events.append(json.loads(payload))

    worker = WorkflowWorker(broadcast)
    loop_task = await _run_worker(worker)

    worker.submit("b1", _wf("n1", "BlockingStep", {"block_seconds": 30}), "null")
    await asyncio.sleep(0.1)  # let the node start its blocking work
    assert worker.cancel_current() is True
    await asyncio.sleep(0.1)  # CancelledError must be delivered at the await point
    # worker loop survives and processes the next queued item
    worker.submit("b2", _wf("n1", "FakeStep", {"value": "next"}), "null")
    await asyncio.sleep(0.2)
    loop_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await loop_task

    done_b1 = next(e for e in events if e["type"] == "execution_done" and e["execution_id"] == "b1")
    assert done_b1["cancelled"] is True
    assert done_b1["result"] is None
    done_b2 = next(e for e in events if e["type"] == "execution_done" and e["execution_id"] == "b2")
    assert done_b2["cancelled"] is False
    assert done_b2["error"] is None

    history = json.loads(worker.history_snapshot())
    assert any(h["execution_id"] == "b1" and h["state"] == "cancelled" for h in history)
    assert any(h["execution_id"] == "b2" and h["state"] == "completed" for h in history)


@pytest.mark.asyncio
async def test_blocking_node_completes_normally() -> None:
    """A short blocking node without interrupt still completes with its result."""
    events: List[Dict[str, Any]] = []

    def broadcast(payload: str) -> None:
        events.append(json.loads(payload))

    worker = WorkflowWorker(broadcast)
    loop_task = await _run_worker(worker)

    worker.submit("b3", _wf("n1", "BlockingStep", {"block_seconds": 0.2}), "null")
    await asyncio.sleep(0.5)
    loop_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await loop_task

    done = next(e for e in events if e["type"] == "execution_done" and e["execution_id"] == "b3")
    assert done["cancelled"] is False
    assert done["result"] == {"blocking_result": {"done": True}}
    assert done["error"] is None


@pytest.mark.asyncio
async def test_malformed_workflow_yields_error_without_killing_worker() -> None:
    """A malformed submission fails one execution without stopping the loop."""
    events: List[Dict[str, Any]] = []

    def broadcast(payload: str) -> None:
        events.append(json.loads(payload))

    worker = WorkflowWorker(broadcast)
    loop_task = await _run_worker(worker)

    worker.submit("e3", "{not json", "null")
    await asyncio.sleep(0.05)
    # worker still alive: second submission is processed
    worker.submit("e4", _wf("n1", "FakeStep", {}), "null")
    await asyncio.sleep(0.05)
    loop_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await loop_task

    ids = [e["execution_id"] for e in events if e["type"] == "execution_done"]
    assert "e3" in ids
    assert "e4" in ids
    err = next(e for e in events if e["type"] == "execution_done" and e["execution_id"] == "e3")
    assert err["error"] is not None


@pytest.mark.asyncio
async def test_huge_result_is_truncated_in_done_and_history() -> None:
    """Oversized results are preview-truncated in both broadcast and history."""
    events: List[Dict[str, Any]] = []

    def broadcast(payload: str) -> None:
        events.append(json.loads(payload))

    worker = WorkflowWorker(broadcast)
    loop_task = await _run_worker(worker)

    raw = "x" * 5000
    wf = json.dumps(
        {
            "nodes": [
                {"id": "n1", "type": "FakeStep", "inputs": {}, "config": {"value": raw}},
                {"id": "n2", "type": "HugeListStep", "inputs": {}, "config": {}},
            ],
            "edges": [],
        }
    )
    worker.submit("e6", wf, "null")
    await asyncio.sleep(0.1)
    loop_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await loop_task

    done = next(e for e in events if e["type"] == "execution_done")
    result = done["result"]
    # Long string value: preview-truncated (not the raw 5000-char payload).
    assert result["fake_result"] != raw
    assert len(result["fake_result"]) == 4000
    assert result["fake_result"].endswith("...")
    assert raw not in json.dumps(done)
    # Huge non-string value: replaced with a short placeholder.
    assert result["big_list"] == "[truncated: list]"

    history = json.loads(worker.history_snapshot())
    entry = next(h for h in history if h["execution_id"] == "e6" and h["state"] == "completed")
    assert entry["result"] == result
    assert raw not in json.dumps(history)


@pytest.mark.asyncio
async def test_history_snapshot_contains_finished_execution() -> None:
    """Finished executions are recorded and visible via history_snapshot."""
    events: List[Dict[str, Any]] = []

    def broadcast(payload: str) -> None:
        events.append(json.loads(payload))

    worker = WorkflowWorker(broadcast)
    loop_task = await _run_worker(worker)

    worker.submit("e5", _wf("n1", "FakeStep", {}), "null")
    await asyncio.sleep(0.05)
    loop_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await loop_task

    history = json.loads(worker.history_snapshot())
    assert any(h["execution_id"] == "e5" and h["state"] == "completed" for h in history)


@pytest.mark.asyncio
async def test_init_context_and_task_input_seed_executor_context() -> None:
    """init_context and dict task_input resolve inside node executions and in the result."""
    events: List[Dict[str, Any]] = []

    def broadcast(payload: str) -> None:
        events.append(json.loads(payload))

    worker = WorkflowWorker(broadcast)
    loop_task = await _run_worker(worker)

    wf = json.dumps(
        {
            "nodes": [
                {"id": "n1", "type": "ContextReadStep", "inputs": {}, "config": {"keys": "greeting,user"}},
            ],
            "edges": [],
            "init_context": {"greeting": "hello-from-init", "user": "init-user"},
        }
    )
    # task_input is a dict: overlaid on init_context, wins on conflict.
    worker.submit("s1", wf, json.dumps({"user": "task-user"}))
    await asyncio.sleep(0.05)
    loop_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await loop_task

    done = next(e for e in events if e["type"] == "execution_done" and e["execution_id"] == "s1")
    assert done["cancelled"] is False
    assert done["error"] is None
    result = done["result"]
    # Node resolved both keys from the seeded context: init_context value for
    # greeting, task_input (overlay) for user.
    assert result["ctx_read"] == {"greeting": "hello-from-init", "user": "task-user"}
    # Seeds are part of the returned result context too.
    assert result["greeting"] == "hello-from-init"
    assert result["user"] == "task-user"


@pytest.mark.asyncio
async def test_scalar_task_input_seeded_under_reserved_key() -> None:
    """A non-dict task_input is seeded under the framework's reserved key."""
    events: List[Dict[str, Any]] = []

    def broadcast(payload: str) -> None:
        events.append(json.loads(payload))

    worker = WorkflowWorker(broadcast)
    loop_task = await _run_worker(worker)

    wf = json.dumps(
        {
            "nodes": [
                {"id": "n1", "type": "ContextReadStep", "inputs": {}, "config": {"keys": "task_input"}},
            ],
            "edges": [],
        }
    )
    worker.submit("s2", wf, json.dumps("plain-scalar"))
    await asyncio.sleep(0.05)
    loop_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await loop_task

    done = next(e for e in events if e["type"] == "execution_done" and e["execution_id"] == "s2")
    assert done["cancelled"] is False
    assert done["error"] is None
    # The scalar lands under the framework's reserved INPUT_KEY ("task_input").
    assert done["result"]["ctx_read"] == {"task_input": "plain-scalar"}
    assert done["result"]["task_input"] == "plain-scalar"

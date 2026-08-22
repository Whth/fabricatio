"""Tests for the no-LLM "Hello Fabricatio" demo blueprint.

The demo must run immediately on a fresh install: two pure-Python actions,
no LLM, no network. These tests pin the blueprint shape, its registry
ports, and an actual offline execution through the real dispatch path.
"""

import asyncio
from collections.abc import Generator

import pytest
from fabricatio_core.models.task import Task
from fabricatio_webui.blueprints import build_blueprints
from fabricatio_webui.executor import (
    _build_workflow,
    _compile_workflow_plan,
    _registry_version,
    _workflow_plan_key,
    build_roles_from_boards,
)

DEMO_BLUEPRINT_ID = "webui-hello-fabricatio"
DEMO_NAMESPACE = "hello-fabricatio"


@pytest.fixture(autouse=True)
def _clear_plan_cache() -> Generator[None, None, None]:
    """Isolate each test with a fresh plan cache."""
    _compile_workflow_plan.cache_clear()
    yield
    _compile_workflow_plan.cache_clear()


def _demo_blueprint():
    """Return the Hello Fabricatio blueprint entry, failing loudly when absent."""
    bp = next((b for b in build_blueprints()["blueprints"] if b["id"] == DEMO_BLUEPRINT_ID), None)
    assert bp is not None, f"{DEMO_BLUEPRINT_ID} not found in the blueprint catalog"
    return bp


class TestDemoBlueprintShape:
    """The demo blueprint ships a complete two-node pipeline."""

    @staticmethod
    def test_is_present_with_two_nodes() -> None:
        """The demo blueprint exists and declares both steps."""
        bp = _demo_blueprint()
        assert bp["category"] == "webui"
        assert bp["node_count"] == 2

    @staticmethod
    def test_tops_the_catalog() -> None:
        """The demo is the first blueprint so it heads the sidebar rail."""
        first = build_blueprints()["blueprints"][0]
        assert first["id"] == DEMO_BLUEPRINT_ID

    @staticmethod
    def test_steps_are_wired_stats_to_stats() -> None:
        """TextStats feeds SummarizeStats through the stats handle."""
        wf_doc = _demo_blueprint()["workflow"]
        types = [n["type"] for n in wf_doc["nodes"]]
        assert types == ["TextStats", "SummarizeStats"]
        edges = wf_doc["edges"]
        assert len(edges) == 1
        assert edges[0]["source"] == "TextStats_1"
        assert edges[0]["source_handle"] == "stats"
        assert edges[0]["target"] == "SummarizeStats_2"
        assert edges[0]["target_handle"] == "stats"

    @staticmethod
    def test_node_types_are_registered_with_ports() -> None:
        """Both demo actions appear in the node registry with matching ports."""
        from fabricatio_webui.registry import build_node_registry

        by_type = {t["type"]: t for t in build_node_registry()["node_types"]}
        stats_out = {p["name"] for p in by_type["TextStats"]["output_ports"]}
        summary_in = {p["name"] for p in by_type["SummarizeStats"]["input_ports"]}
        assert "stats" in stats_out
        assert "stats" in summary_in


class TestDemoOfflineExecution:
    """The demo executes end-to-end without any LLM call."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_direct_serve_counts_and_summarizes() -> None:
        """Serving the compiled workflow produces the formatted summary."""
        wf_doc = _demo_blueprint()["workflow"]
        plan = _compile_workflow_plan(_registry_version(), _workflow_plan_key(wf_doc))
        workflow = _build_workflow(plan)

        task = Task(name="demo-direct")
        task.update_init_context(text="The quick brown fox")
        await workflow.serve(task)

        out = await task.get_output()
        assert task.is_finished()
        assert out == "[demo] chars: 19, words: 4, lines: 1"

    @staticmethod
    @pytest.mark.asyncio
    async def test_dispatched_role_serves_published_task() -> None:
        """A board containing the demo serves a published task on its namespace."""
        wf_doc = _demo_blueprint()["workflow"]
        board = {
            "format_version": 2,
            "name": "demo-board",
            "roles": [
                {
                    "name": "greeter",
                    "description": "",
                    "workflows": [
                        {
                            "name": wf_doc["name"],
                            "namespace": DEMO_NAMESPACE,
                            "nodes": wf_doc["nodes"],
                            "edges": wf_doc["edges"],
                            "init_context": {},
                            "task_output_key": wf_doc["task_output_key"],
                        }
                    ],
                }
            ],
            "actions": [],
        }
        roles = build_roles_from_boards([board])
        assert len(roles) == 1
        try:
            task = Task(name="first-run", send_to=[DEMO_NAMESPACE])
            task.update_init_context(text="The quick brown fox")
            task.publish()
            out = await asyncio.wait_for(task.get_output(), timeout=5)
            assert task.is_finished()
            assert out == "[demo] chars: 19, words: 4, lines: 1"
        finally:
            for role in roles:
                role.undo_dispatch()

    @staticmethod
    @pytest.mark.asyncio
    async def test_empty_input_still_serves() -> None:
        """Publishing without ``text`` degrades gracefully to empty-input stats."""
        wf_doc = _demo_blueprint()["workflow"]
        plan = _compile_workflow_plan(_registry_version(), _workflow_plan_key(wf_doc))
        workflow = _build_workflow(plan)

        task = Task(name="demo-empty")
        await workflow.serve(task)

        out = await task.get_output()
        assert out == "[demo] chars: 0, words: 0, lines: 0"

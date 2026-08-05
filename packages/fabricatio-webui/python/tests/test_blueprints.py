"""Tests for the package-defined blueprint builder."""

from pathlib import Path
from typing import Any

import pytest

from fabricatio_webui.blueprints import (
    _collect_workflows,
    _graph_from_workflow,
    _output_key,
    _slugify,
    build_blueprints,
)
from fabricatio_webui.executor import _compile_workflow_plan, _registry_version, _workflow_plan_key


class TestSlugify:
    """_slugify turns a workflow name into a lowercase dashed id suffix."""

    @staticmethod
    def test_basic():
        assert _slugify("Write Novel") == "write-novel"

    @staticmethod
    def test_preserves_alphanumeric():
        assert _slugify("Generate a Novel Draft") == "generate-a-novel-draft"

    @staticmethod
    def test_strips_empty_parts():
        assert _slugify("---") == ""


class TestOutputKey:
    """_output_key mirrors the registry's output port naming."""

    @staticmethod
    def test_explicit_output_key():
        from fabricatio_novel.actions.novel import GenerateNovelDraft

        assert _output_key(GenerateNovelDraft) == "novel_draft"

    @staticmethod
    def test_falls_back_to_class_lower():
        from fabricatio_actions.actions.output import PersistentAll

        assert _output_key(PersistentAll) == "persistent_count"


class TestCollectWorkflows:
    """_collect_workflows finds WorkFlow objects in the configured packages."""

    @staticmethod
    def test_yields_pairs():
        pairs = list(_collect_workflows())
        assert all(isinstance(cat, str) and hasattr(wf, "name") for cat, wf in pairs)

    @staticmethod
    def test_categories_are_novel_or_typst():
        pairs = list(_collect_workflows())
        cats = {cat for cat, _ in pairs}
        assert cats <= {"novel", "typst"}

    @staticmethod
    def test_novel_workflows_present():
        pairs = list(_collect_workflows())
        novel_names = {wf.name for cat, wf in pairs if cat == "novel"}
        # The "Write Novel Workflow" must be present (it's a headline workflow in the package).
        assert any("writenovel" in wf.name.lower() for _, wf in pairs if wf.name)


class TestBuildBlueprints:
    """build_blueprints produces a well-formed catalog."""

    @staticmethod
    def test_returns_expected_top_level_keys():
        result = build_blueprints()
        assert "version" in result
        assert "blueprints_version" in result
        assert "blueprints" in result

    @staticmethod
    def test_blueprints_list_is_non_empty():
        result = build_blueprints()
        assert len(result["blueprints"]) > 0

    @staticmethod
    def test_each_blueprint_has_required_fields():
        result = build_blueprints()
        for bp in result["blueprints"]:
            assert "id" in bp
            assert "name" in bp
            assert "description" in bp
            assert "category" in bp
            assert "node_count" in bp
            assert "workflow" in bp

    @staticmethod
    def test_blueprint_ids_are_unique():
        result = build_blueprints()
        ids = [bp["id"] for bp in result["blueprints"]]
        assert len(ids) == len(set(ids)), "Blueprint ids must be unique"

    @staticmethod
    def test_blueprint_workflow_json_dumps():
        result = build_blueprints()
        for bp in result["blueprints"]:
            import json

            # Must round-trip without a custom default serializer.
            json.dumps(bp["workflow"])

    @staticmethod
    def test_node_ids_unique_per_workflow():
        result = build_blueprints()
        for bp in result["blueprints"]:
            node_ids = [n["id"] for n in bp["workflow"]["nodes"]]
            assert len(node_ids) == len(set(node_ids)), f"Duplicate node ids in {bp['id']}"

    @staticmethod
    def test_edge_ids_unique_per_workflow():
        result = build_blueprints()
        for bp in result["blueprints"]:
            edge_ids = [e["id"] for e in bp["workflow"]["edges"]]
            assert len(edge_ids) == len(set(edge_ids)), f"Duplicate edge ids in {bp['id']}"

    @staticmethod
    def test_edge_targets_reference_existing_nodes():
        result = build_blueprints()
        for bp in result["blueprints"]:
            node_ids = {n["id"] for n in bp["workflow"]["nodes"]}
            for edge in bp["workflow"]["edges"]:
                assert edge["source"] in node_ids, f"Bad source in {bp['id']}: {edge}"
                assert edge["target"] in node_ids, f"Bad target in {bp['id']}: {edge}"

    @staticmethod
    def test_node_types_are_strings():
        result = build_blueprints()
        for bp in result["blueprints"]:
            for node in bp["workflow"]["nodes"]:
                assert isinstance(node["type"], str)
                assert isinstance(node["id"], str)

    @staticmethod
    def test_node_positions_are_numeric_pairs():
        result = build_blueprints()
        for bp in result["blueprints"]:
            for node in bp["workflow"]["nodes"]:
                assert isinstance(node["pos"], list)
                assert len(node["pos"]) == 2
                assert isinstance(node["pos"][0], (int, float))
                assert isinstance(node["pos"][1], (int, float))


class TestWriteNovelWorkflowStructure:
    """Spot-check the WriteNovelWorkflow blueprint (the headline one-step pipeline)."""

    @staticmethod
    def test_has_three_nodes():
        result = build_blueprints()
        bp = next(
            (b for b in result["blueprints"] if b["id"] == "novel-writenovelworkflow"),
            None,
        )
        assert bp is not None, "novel-write-novel-workflow not found"
        assert bp["node_count"] == 3, f"Expected 3 nodes, got {bp['node_count']}"
        assert len(bp["workflow"]["nodes"]) == 3

    @staticmethod
    def test_has_chained_edges():
        result = build_blueprints()
        bp = next(
            (b for b in result["blueprints"] if b["id"] == "novel-writenovelworkflow"),
            None,
        )
        assert bp is not None
        # GenerateNovel → DumpNovel → PersistentAll: every consecutive pair is
        # wired (novel → novel field; DumpNovel output → context display port).
        edges = bp["workflow"]["edges"]
        assert len(edges) == 2
        assert edges[0]["source_handle"] == "novel"
        assert edges[0]["target_handle"] == "novel"
        assert edges[1]["target_handle"] == "context"

    @staticmethod
    def test_first_node_is_generate_novel():
        result = build_blueprints()
        bp = next(
            (b for b in result["blueprints"] if b["id"] == "novel-writenovelworkflow"),
            None,
        )
        nodes = bp["workflow"]["nodes"]
        assert nodes[0]["type"] == "GenerateNovel"


class TestBlueprintGraphConnectivity:
    """Blueprint graphs must be fully renderable: every node type must exist
    in the node registry and every edge handle must match a port on the
    source/target node. A broken handle silently drops the edge in VueFlow —
    the "no connections" symptom."""

    @staticmethod
    def test_every_blueprint_node_type_is_registered():
        from fabricatio_webui.registry import build_node_registry

        registry_types = {t["type"] for t in build_node_registry()["node_types"]}
        result = build_blueprints()
        for bp in result["blueprints"]:
            for node in bp["workflow"]["nodes"]:
                assert node["type"] in registry_types, (
                    f"{bp['id']}: node type {node['type']} missing from the node registry"
                )

    @staticmethod
    def test_every_edge_handle_matches_a_port():
        from fabricatio_webui.registry import build_node_registry

        by_type = {t["type"]: t for t in build_node_registry()["node_types"]}
        result = build_blueprints()
        for bp in result["blueprints"]:
            nodes = {n["id"]: n for n in bp["workflow"]["nodes"]}
            for edge in bp["workflow"]["edges"]:
                src = nodes[edge["source"]]
                tgt = nodes[edge["target"]]
                out_ports = {p["name"] for p in by_type[src["type"]]["output_ports"]}
                in_ports = {p["name"] for p in by_type[tgt["type"]]["input_ports"]}
                assert edge["source_handle"] in out_ports, (
                    f"{bp['id']}: {edge['id']} source handle {edge['source_handle']} "
                    f"is not an output port of {src['type']}"
                )
                assert edge["target_handle"] in in_ports, (
                    f"{bp['id']}: {edge['id']} target handle {edge['target_handle']} "
                    f"is not an input port of {tgt['type']}"
                )

    @staticmethod
    def test_multi_node_blueprints_are_fully_chained():
        result = build_blueprints()
        for bp in result["blueprints"]:
            nodes = bp["workflow"]["nodes"]
            edges = bp["workflow"]["edges"]
            if len(nodes) > 1:
                # Every consecutive step pair is dataflow-connected (field,
                # runtime param, or whole-context display wire).
                assert len(edges) == len(nodes) - 1, f"{bp['id']}: expected {len(nodes) - 1} edges, got {len(edges)}"

    @staticmethod
    def test_typst_outline_has_param_wired_edges():
        result = build_blueprints()
        bp = next(
            (b for b in result["blueprints"] if b["id"] == "typst-generate-article-outline"),
            None,
        )
        assert bp is not None
        edges = bp["workflow"]["edges"]
        assert len(edges) == 2
        # GenerateArticleProposal → GenerateInitialOutline: proposal is a
        # runtime _execute parameter, not a model field.
        assert edges[0]["source_handle"] == "article_proposal"
        assert edges[0]["target_handle"] == "article_proposal"
        # GenerateInitialOutline → DumpFinalizedOutput: the outline lands on
        # the single required runtime parameter (to_dump).
        assert edges[1]["target_handle"] == "to_dump"


class TestBlueprintsCompileToExecutablePlans:
    """Every blueprint's workflow doc must compile to an executable plan.

    This is the strongest correctness check: it validates that all node types
    resolve to Action subclasses, all configs instantiate, and the topo sort
    succeeds.
    """

    @staticmethod
    def test_all_blueprints_compile():
        result = build_blueprints()
        reg_ver = _registry_version()
        errors: list[str] = []

        for bp in result["blueprints"]:
            wf_doc = bp["workflow"]
            plan_key = _workflow_plan_key(wf_doc)
            try:
                _compile_workflow_plan(reg_ver, plan_key)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{bp['id']}: {exc}")

        assert not errors, f"Blueprint plan compilation failures:\n" + "\n".join(errors)

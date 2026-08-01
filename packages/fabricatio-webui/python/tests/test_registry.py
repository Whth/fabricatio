"""Tests for registry widget hints, versions, and executor previews."""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fabricatio_core.models.action import Action
from fabricatio_webui.executor import _preview
from fabricatio_webui.registry import _widget_hint, build_node_registry, migrate_workflow
from pydantic import Field


class WidgetProbe(Action):
    """Registry probe action exercising the widget table."""

    name: str = "probe"
    enabled: bool = True
    count: int = 3
    ratio: float = 0.5
    mode: Literal["fast", "slow"] = "fast"
    note: str = "short"
    long_note: str = "x" * 200
    path: Path = Path("probe_path.txt")
    items: List[str] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(default_factory=dict)
    output_key: str = "probe_result"

    async def _execute(self, **cxt: Any) -> Any:
        return None


def test_widget_hint_table() -> None:
    """The annotation-to-widget table matches the spec (§2.3)."""
    assert _widget_hint(bool, True, True)["widget"] == "toggle"
    assert _widget_hint(int, True, 3) == {"widget": "number", "step": 1}
    assert _widget_hint(float, True, 0.5) == {"widget": "number", "step": 0.1}
    combo = _widget_hint(Literal["fast", "slow"], True, "fast")
    assert combo["widget"] == "combo"
    assert combo["options"] == ["fast", "slow"]
    assert _widget_hint(str, True, "short")["widget"] == "text"
    assert _widget_hint(str, True, "x" * 200)["widget"] == "textarea"
    assert _widget_hint(Path, True, Path("probe_path.txt"))["widget"] == "text"
    assert _widget_hint(List[str], True, [])["widget"] == "text"
    assert _widget_hint(Dict[str, Any], True, {})["widget"] == "json"
    assert _widget_hint(Any, True, None)["widget"] == "json"
    optional = _widget_hint(Optional[str], True, None)
    assert optional["widget"] == "text"


def test_registry_entries_carry_schema_version_and_registry_version() -> None:
    """Every registry entry and the registry itself carry sha1 versions."""
    reg = build_node_registry()
    assert "registry_version" in reg
    assert len(reg["registry_version"]) == 8
    by_type = {n["type"]: n for n in reg["node_types"]}
    probe = by_type.get("WidgetProbe")
    assert probe is not None, "WidgetProbe missing from registry"
    assert len(probe["schema_version"]) == 8
    widgets = {f["name"]: f.get("widget") for f in probe["config_fields"]}
    assert widgets["enabled"] == "toggle"
    assert widgets["count"] == "number"
    assert widgets["mode"] == "combo"
    assert widgets["path"] == "text"


def test_migrate_workflow_upgrades_legacy_format() -> None:
    """A legacy workflow is upgraded to format_version 1 with a summary."""
    legacy = {
        "version": "1.0",
        "name": "old",
        "nodes": [{"id": "n1", "type": "WidgetProbe", "inputs": {}, "config": {}}],
        "edges": [],
        "init_context": {},
    }
    reg = build_node_registry()
    migrated, summary = migrate_workflow(legacy, reg)
    assert migrated["format_version"] == 1
    assert migrated["nodes"][0]["schema_version"] >= 0
    assert "format_version" in summary


def test_migrate_workflow_does_not_mutate_input() -> None:
    """Migration rebuilds the workflow dict and edge defaults."""
    legacy = {
        "version": "1.0",
        "nodes": [{"id": "n1", "type": "WidgetProbe"}],
        "edges": [{"id": "e1", "source": "s", "target": "n1"}],
    }
    reg = build_node_registry()
    migrated, _ = migrate_workflow(legacy, reg)
    assert "format_version" not in legacy
    assert "schema_version" not in legacy["nodes"][0]
    assert migrated["nodes"][0]["schema_version"] == 1
    assert migrated["edges"][0]["source_handle"] == "default"
    assert migrated["edges"][0]["target_handle"] == "default"


def test_executor_preview_truncates_long_outputs() -> None:
    """_preview renders JSON and truncates past the limit."""
    assert _preview({"a": 1}) == '{"a": 1}'
    long = "y" * 5000
    assert len(_preview(long)) <= 4000

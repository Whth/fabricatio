"""Registry public API — full registry build and document migration."""

import hashlib
import inspect
import json
from functools import cache
from typing import Any, Dict, List

from fabricatio_core.journal import logger

from fabricatio_webui.registry._category import _derive_category
from fabricatio_webui.registry._constants import CONTEXT_PORT_NAME
from fabricatio_webui.registry._discover import _concrete_action_subclasses, _discover_action_modules
from fabricatio_webui.registry._execute import _consumes_context, _execute_params
from fabricatio_webui.registry._ports import _extract_capabilities, _extract_input_ports, _extract_output_ports


def build_node_registry() -> Dict[str, Any]:
    """Build the full node type registry for the frontend.

    Returns a dict with:
      - ``version``: registry format version
      - ``node_types``: list of node type descriptors, each with:
        type, title, description, category, input_ports, output_ports,
        capabilities, ctx_override
    """
    # Auto-discover action modules so __subclasses__() finds them.
    _discover_action_modules()

    node_types: List[Dict[str, Any]] = []
    concrete = _concrete_action_subclasses()
    logger.info(f"Building node registry: discovered {len(concrete)} concrete Action subclass(es).")

    for cls in sorted(concrete, key=lambda c: c.__name__):
        try:
            doc = (cls.__doc__ or "").strip()
            first_line = doc.split("\n")[0].strip() if doc else ""

            # __source__ is set by PyO3 stubgen for Rust-backed actions that
            # have no real Python source; fall back gracefully.
            source_lines: str = getattr(cls, "__source__", None) or ""
            if not source_lines:
                try:
                    source_lines = inspect.getsource(cls)
                except Exception:  # noqa: BLE001
                    source_lines = ""

            model_ports = _extract_input_ports(cls)

            # Runtime _execute parameters become read-only input ports (wired
            # from a predecessor's output; never config-editable — they are
            # not model fields).  A whole-context consumer additionally gets
            # the CONTEXT_PORT_NAME display port so blueprint graphs can show
            # the implicit context dataflow between steps.
            seen = {p["name"] for p in model_ports}
            runtime_ports: List[Dict[str, Any]] = []
            for param_name in _execute_params(cls):
                if param_name in seen:
                    continue
                seen.add(param_name)
                runtime_ports.append(
                    {
                        "name": param_name,
                        "type": "Any",
                        "optional": True,
                        "description": f"Runtime parameter of {cls.__name__}, resolved from the workflow context",
                        "widget": "text",
                    }
                )
            if _consumes_context(cls) and CONTEXT_PORT_NAME not in seen:
                runtime_ports.append(
                    {
                        "name": CONTEXT_PORT_NAME,
                        "type": "Any",
                        "optional": True,
                        "description": "Whole execution context from preceding steps (display-only wire)",
                        "widget": "text",
                    }
                )

            entry: Dict[str, Any] = {
                "type": cls.__name__,
                "title": first_line or cls.__name__,
                "description": doc,
                "category": _derive_category(cls),
                "input_ports": [*model_ports, *runtime_ports],
                "output_ports": _extract_output_ports(cls),
                "capabilities": _extract_capabilities(cls),
                "ctx_override": getattr(cls, "ctx_override", False),
                # Only model fields are editable config; runtime params are
                # dataflow-only and must never reach cls(**config).
                "config_fields": model_ports,
                # Raw Python source for the read-only source viewer.
                "source_code": source_lines,
            }
            # Content hash for change detection; the wire node field
            # ``schema_version`` is a numeric generation marker, not this hash.
            entry["schema_version"] = hashlib.sha1(json.dumps(entry, sort_keys=True, default=str).encode()).hexdigest()[  # noqa: S324
                :8
            ]
            node_types.append(entry)
        except Exception:  # noqa: BLE001
            logger.warn(f"Failed to introspect Action subclass {cls.__name__!r}; skipping.")

    node_types_json = json.dumps(node_types, sort_keys=True, default=str)
    return {
        "version": "1.0",
        "registry_version": hashlib.sha1(node_types_json.encode()).hexdigest()[:8],  # noqa: S324
        "node_types": node_types,
    }


@cache
def _worker_registry() -> Dict[str, Any]:
    """Return a cached registry for the execution worker (built once)."""
    return build_node_registry()


def migrate_workflow(wf: Dict[str, Any], registry: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
    """Upgrade a legacy workflow dict to the current format.

    Returns ``(workflow, summary)`` where *summary* describes what changed.
    Never mutates the input dict — the workflow is rebuilt. Idempotent: a
    current-format workflow is returned with summary ``"no changes"``.
    """
    changes: List[str] = []
    wf = dict(wf)
    if wf.get("format_version", 0) < 1:
        wf["format_version"] = 1
        changes.append("format_version -> 1")

    by_type = {n["type"]: n for n in registry.get("node_types", [])}
    nodes: List[Dict[str, Any]] = []
    for raw_node in wf.get("nodes", []):
        node = dict(raw_node)
        node.setdefault("inputs", {})
        node.setdefault("config", {})
        if node.get("schema_version", 0) < 1:
            node["schema_version"] = 1 if node.get("type") in by_type else 0
            changes.append(f"node {node.get('id', '?')} schema_version pinned")
        nodes.append(node)
    wf["nodes"] = nodes

    edges: List[Dict[str, Any]] = []
    for raw_edge in wf.get("edges", []):
        edge = dict(raw_edge)
        edge.setdefault("source_handle", "default")
        edge.setdefault("target_handle", "default")
        edges.append(edge)
    wf["edges"] = edges
    wf.setdefault("init_context", {})
    return wf, ", ".join(changes) or "no changes"


def migrate_board(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Upgrade a saved document to the board format (``format_version`` 2).

    Legacy workflow documents (formats 0/1) become boards holding one role
    with one workflow. Boards pass through unchanged. Mirrors the Rust-side
    ``BoardJson::migrate_legacy`` used when loading the store.
    """
    raw = dict(raw)
    if raw.get("format_version", 0) >= 2 or "roles" in raw:
        raw["format_version"] = 2
        raw.setdefault("roles", [])
        raw.setdefault("actions", [])
        return raw

    name = str(raw.get("name") or "Untitled Board")
    description = str(raw.get("description") or "")
    workflow, _ = migrate_workflow(raw, _worker_registry())
    return {
        "version": "1.0",
        "format_version": 2,
        "name": name,
        "description": description,
        "roles": [
            {
                "name": name,
                "description": description,
                "workflows": [
                    {
                        "name": name,
                        "namespace": name,
                        "task_output_key": None,
                        "nodes": workflow.get("nodes", []),
                        "edges": workflow.get("edges", []),
                        "init_context": workflow.get("init_context", {}),
                    }
                ],
            }
        ],
        "actions": [],
        "meta": raw.get("meta"),
    }

"""Package-defined workflow blueprints for the webui board sidebar."""

import contextlib
import hashlib
import importlib
import json
import pkgutil
from typing import Any, Dict, Iterator, List, Tuple, Type

from fabricatio_core.models.action import Action, WorkFlow
from pydantic.fields import FieldInfo

from fabricatio_webui.discovery import installed_fabricatio_packages
from fabricatio_webui.registry import (
    CONTEXT_PORT_NAME,
    _consumes_context,
    _execute_params,
    _required_execute_params,
)

#: Workflow sources are discovered dynamically: every installed
#: ``fabricatio_*`` package's ``workflows`` subpackage is scanned, with
#: ``fabricatio_webui`` pinned first so the no-LLM demo tops the rail.

#: Action infrastructure fields that never become node config.
_INFRA_FIELDS = {"name", "description", "output_key"}

#: Graph layout: one vertical column of nodes.
_NODE_X = 60
_NODE_Y_STEP = 160
_NODE_Y_START = 40


def _slugify(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in text.lower())
    return "-".join(part for part in cleaned.split("-") if part)


def _output_key(cls: Type[Action]) -> str:
    return (
        getattr(cls, "output_key", "")
        or cls.model_fields.get("output_key", FieldInfo(default="")).default
        or cls.__name__.lower()
    )


def _iter_workflow_modules() -> Iterator[Any]:
    for pkg in installed_fabricatio_packages():
        try:
            top = importlib.import_module(f"{pkg}.workflows")
        except ImportError:
            continue
        yield top
        path = getattr(top, "__path__", None)
        if path is None:
            continue
        for mod_info in pkgutil.iter_modules(path):
            with contextlib.suppress(Exception):
                yield importlib.import_module(f"{pkg}.workflows.{mod_info.name}")


def _collect_workflows() -> Iterator[Tuple[str, WorkFlow]]:
    for module in _iter_workflow_modules():
        category = module.__name__.split(".")[0].removeprefix("fabricatio_")
        for value in vars(module).values():
            if isinstance(value, WorkFlow):
                yield category, value


def _step_config(step: Action) -> Dict[str, Any]:
    dumped = step.model_dump(exclude=_INFRA_FIELDS, exclude_none=True)
    return json.loads(json.dumps(dumped, default=str))


def _graph_from_workflow(
    wf: WorkFlow,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    prev: Tuple[str, str, str] | None = None

    for index, step in enumerate(wf.iter_actions()):
        type_name = type(step).__name__
        node_id = f"{type_name}_{index + 1}"
        nodes.append(
            {
                "id": node_id,
                "type": type_name,
                "title": type_name,
                "pos": [_NODE_X, _NODE_Y_START + index * _NODE_Y_STEP],
                "inputs": {},
                "config": _step_config(step),
                "schema_version": 1,
            }
        )
        if prev is not None:
            prev_id, prev_instance_key, prev_port_key = prev
            target_handle = _wire_target(step, prev_instance_key)
            if target_handle is not None:
                edges.append(
                    {
                        "id": f"e_{prev_id}_{prev_instance_key}_{node_id}_{target_handle}",
                        "source": prev_id,
                        # Renderable port name: instances may override output_key
                        # (e.g. DumpNovel(output_key="task_output")), but the
                        # node's output port comes from the class default.
                        "source_handle": prev_port_key,
                        "target": node_id,
                        "target_handle": target_handle,
                    }
                )
        # The *instance* output_key is what lands in the workflow context at
        # runtime (steps may override it, e.g. ExtractArticleEssence(output_key="documents")).
        instance_key = step.output_key or _output_key(type(step))
        prev = (node_id, instance_key, _output_key(type(step)))

    return nodes, edges


def _wire_target(step: Action, prev_key: str) -> str | None:
    """Find the next step's input handle for the previous step's output key.

    Hierarchical, matching the runtime dataflow:
      1. exact model field (editable config wire),
      2. exact non-plumbing ``_execute`` parameter (context-resolved input),
      3. the single required non-plumbing parameter (e.g. DumpFinalizedOutput
         receives the outline via ``to_dump``),
      4. the whole-context display port when the step consumes ``**context``.
    Returns None when the step takes no dataflow input at all.
    """
    step_type = type(step)
    if prev_key in step_type.model_fields:
        return prev_key
    if prev_key in _execute_params(step_type):
        return prev_key
    required = _required_execute_params(step_type)
    if len(required) == 1:
        return required[0]
    if _consumes_context(step_type):
        return CONTEXT_PORT_NAME
    return None


def _workflow_doc(wf: WorkFlow) -> Dict[str, Any]:
    nodes, edges = _graph_from_workflow(wf)
    steps = list(wf.iter_actions())
    task_output_key = steps[-1].output_key or (_output_key(type(steps[-1])) if steps else "")
    return {
        "name": wf.name,
        "namespace": _slugify(wf.name),
        "task_output_key": task_output_key,
        "nodes": nodes,
        "edges": edges,
        "init_context": {},
    }


def build_blueprints() -> Dict[str, Any]:
    """Collect all workflows into blueprint dicts and return the versioned payload with a content fingerprint."""
    blueprints: List[Dict[str, Any]] = []
    for category, wf in _collect_workflows():
        name = wf.name or type(wf).__name__
        blueprints.append(
            {
                "id": f"{category}-{_slugify(name)}",
                "name": name,
                "description": wf.description or "",
                "category": category,
                "node_count": len(list(wf.iter_actions())),
                "workflow": _workflow_doc(wf),
            }
        )

    fingerprint = hashlib.sha256(json.dumps(blueprints, sort_keys=True, default=str).encode()).hexdigest()[:8]
    return {
        "version": "1.0",
        "blueprints_version": fingerprint,
        "blueprints": blueprints,
    }

"""Action introspection registry for the fabricatio-webui workflow editor.

Discovers all concrete Action subclasses and produces a node type registry
suitable for frontend rendering as a ComfyUI-style node palette.
"""

import contextlib
import hashlib
import inspect
import json
from collections import deque
from functools import cache
from pathlib import Path
from types import UnionType
from typing import (
    Annotated,
    Any,
    Dict,
    List,
    Literal,
    Set,
    Type,
    Union,
    get_args,
    get_origin,
)

from fabricatio_core.journal import logger
from fabricatio_core.models.action import Action
from pydantic.fields import FieldInfo

# ---------------------------------------------------------------------------
# Excluded fields — fields that belong to the Action base / infrastructure
# and should never become input ports.
# ---------------------------------------------------------------------------
try:
    from fabricatio_core.models.role import EXCLUDED_FIELDS as _ROLE_EXCLUDED
except ImportError:
    _ROLE_EXCLUDED = None

_HARD_EXCLUDED: Set[str] = {"name", "description", "output_key", "ctx_override"}

if _ROLE_EXCLUDED is not None:
    EXCLUDED_FIELDS: Set[str] = _HARD_EXCLUDED | _ROLE_EXCLUDED
else:
    EXCLUDED_FIELDS = _HARD_EXCLUDED

# ---------------------------------------------------------------------------
# Runtime _execute parameters — the second dataflow surface.
#
# Action subclasses receive data two ways: declared model fields (editable
# config, instantiated via cls(**config)) and the framework-injected context
# that lands on the *_execute* signature when the WorkFlow runner calls
# ``_execute(**context)``.  Model fields become config fields; *runtime
# parameters* become read-only input ports so blueprint graphs can wire them
# (e.g. GenerateInitialOutline's ``article_proposal``).
# ---------------------------------------------------------------------------

#: _execute parameter names that are framework plumbing, never dataflow ports.
_RUNTIME_PLUMBING: Set[str] = {
    "self",
    "_",
    "cxt",
    "ctx",
    "context",
    "supervisor",
    "task_input",
    "task_output",
    "args",
    "kwargs",
}

#: Port name for whole-context display wires (see _consumes_context).
CONTEXT_PORT_NAME = "context"


def _execute_params(cls: Type[Action]) -> List[str]:
    """Non-plumbing named parameters of *cls*._execute (no **kwargs)."""
    params: List[str] = []
    try:
        sig = inspect.signature(cls._execute)
    except (TypeError, ValueError):
        return params
    for name, param in sig.parameters.items():
        if name in _RUNTIME_PLUMBING:
            continue
        if param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY):
            params.append(name)
    return params


def _required_execute_params(cls: Type[Action]) -> List[str]:
    """Non-plumbing _execute parameters without a default value."""
    try:
        sig = inspect.signature(cls._execute)
    except (TypeError, ValueError):
        return []
    required = []
    for name, param in sig.parameters.items():
        if name in _RUNTIME_PLUMBING:
            continue
        if param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY) and param.default is param.empty:
            required.append(name)
    return required


def _consumes_context(cls: Type[Action]) -> bool:
    """True when *cls*._execute receives the whole workflow context.

    Either via a ``**kwargs`` catch-all (novel actions take ``**cxt``) or a
    named context parameter.  Such steps are dataflow-connected to every
    predecessor through the shared context even without a field match.
    """
    try:
        sig = inspect.signature(cls._execute)
    except (TypeError, ValueError):
        return False
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()) or any(
        name in {"cxt", "ctx", "context"} for name in sig.parameters
    )


# ---------------------------------------------------------------------------
# Category derivation
# ---------------------------------------------------------------------------


def _mro_class_names(cls: type) -> Set[str]:
    """Return the set of class names in *cls*'s MRO."""
    return {c.__name__ for c in cls.__mro__}


def _derive_category(cls: type) -> str:  # noqa: PLR0911
    """Derive the node-palette category from an Action subclass's MRO."""
    mro = _mro_class_names(cls)
    class_name = cls.__name__

    # Capability-based categories (checked before name heuristics).
    has_llm = bool({"UseLLM", "Propose"} & mro)

    if {"NovelCompose", "IllustratedNovelCompose"} & mro:
        return "novel"
    if "Comfyui" in mro:
        return "comfyui"
    if {"LancedbRAG", "MilvusRAG"} & mro:
        return "rag"
    if {"GenerateDeck", "GenerateAnalysis"} & mro:
        return "anki"
    if "CharacterCompose" in mro:
        return "character"

    # Name-based heuristics — only apply when no LLM capability is present.
    if not has_llm:
        if any(kw in class_name for kw in ("Read", "Dump", "Write")):
            return "io"
        if any(kw in class_name for kw in ("Forward", "Gather", "Connect")):
            return "data"

    # Broad LLM capability goes to 'llm' unless already captured above.
    if has_llm:
        return "llm"

    return "general"


# ---------------------------------------------------------------------------
# Type-annotation helpers
# ---------------------------------------------------------------------------


def _type_to_port_type(ann: Any) -> str:  # noqa: PLR0911
    """Convert a Python type annotation into a frontend-friendly string."""
    origin = get_origin(ann)

    if origin is not None:
        origin_name = getattr(origin, "__name__", str(origin))
        args = get_args(ann)

        if origin is type(None) or origin is None:
            return "None"

        if origin in (Union, UnionType) and args:
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return f"{_type_to_port_type(non_none[0])}?"
            if non_none:
                # Multi-member union (e.g. str | Path): the registry cannot
                # enumerate members — keep the wildcard so any output fits.
                return "Union"
            return "None"

        if origin is Annotated and args:
            return _type_to_port_type(args[0])

        if origin_name in ("list", "List"):
            if args:
                inner_str = _type_to_port_type(args[0])
                return f"List[{inner_str}]"
            return "List"

        if origin_name == "Literal":
            return "Literal"

        # generic aliases e.g. Task[T]
        return origin_name

    # Plain type
    if isinstance(ann, type):
        if issubclass(ann, Path):
            return "Path"
        if hasattr(ann, "__name__"):
            return ann.__name__
        return str(ann)

    return str(ann)


def _widget_hint(ann: Any, has_default: bool, default: Any) -> Dict[str, Any]:  # noqa: C901, PLR0911
    """Map a field annotation to a frontend widget hint (see spec §2.3).

    Returns ``{"widget": ...}`` plus optional constraints. The port's own
    ``default`` field carries the value; hints only describe the control.
    """
    origin = get_origin(ann)
    args = get_args(ann) if origin is not None else ()

    # Optional[T] / T | None -> T; multi-member unions -> first non-None member.
    # Both typing.Union and PEP 604 (types.UnionType) must unwrap — the latter
    # used to fall through to the JSON catch-all and render as a textarea.
    if origin in (Union, UnionType) and args:
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            hint = _widget_hint(non_none[0], has_default, default)
            if type(None) in args:
                hint["required"] = False
            return hint

    # Annotated[T, Field(...)] -> T; pydantic moves Field() bounds into
    # FieldInfo.metadata as annotated_types Ge/Le/Gt/Lt/MultipleOf objects.
    if origin is Annotated and args:
        hint = _widget_hint(args[0], has_default, default)
        if hint.get("widget") == "number":
            _apply_number_constraints(hint, ann)
        return hint

    if origin is Literal:
        return {"widget": "combo", "options": list(args)}

    if origin is not None and getattr(origin, "__name__", "") in ("list", "List"):
        return {"widget": "text", "separator": ","}

    if origin is not None and getattr(origin, "__name__", "") in ("dict", "Dict"):
        return {"widget": "json"}

    if isinstance(ann, type):
        if issubclass(ann, bool):
            return {"widget": "toggle"}
        if issubclass(ann, int):
            return {"widget": "number", "step": 1}
        if issubclass(ann, float):
            return {"widget": "number", "step": 0.1}
        if issubclass(ann, Path):
            return {"widget": "text", "placeholder": "/path/to/file"}
        if issubclass(ann, str):
            if has_default and isinstance(default, str) and len(default) > 120:
                return {"widget": "textarea"}
            return {"widget": "text"}

    # Anything else / unresolvable
    return {"widget": "json"}


def _apply_number_constraints(hint: Dict[str, Any], ann: Any) -> None:
    """Copy numeric bounds from Annotated metadata into a hint.

    Constraints arrive in two shapes: ``Annotated[float, Field(ge=…)]``
    wraps a FieldInfo whose ``.metadata`` holds annotated_types objects,
    while pydantic constrained types (``NonNegativeFloat`` = ``Annotated[
    float, Ge(0)]``) put the Ge/Le/Gt/Lt/MultipleOf objects directly in
    ``__metadata__``. The frontend number widget renders them as
    min/max/step.
    """
    for meta in getattr(ann, "__metadata__", ()):
        items = getattr(meta, "metadata", ()) if isinstance(meta, FieldInfo) else (meta,)
        for c in items:
            if hasattr(c, "ge") and "min" not in hint:
                hint["min"] = c.ge
            if hasattr(c, "gt") and "min" not in hint:
                hint["min"] = c.gt
            if hasattr(c, "le") and "max" not in hint:
                hint["max"] = c.le
            if hasattr(c, "lt") and "max" not in hint:
                hint["max"] = c.lt
            if hasattr(c, "multiple_of") and "step" not in hint:
                hint["step"] = c.multiple_of


def _annotation_to_schema(ann: Any) -> Dict[str, Any]:
    """Produce a full port-schema dict from a type annotation."""
    type_str = _type_to_port_type(ann)
    schema: Dict[str, Any] = {"type": type_str}

    origin = get_origin(ann)
    if origin is not None:
        origin_name = getattr(origin, "__name__", str(origin))
        args = get_args(ann)

        has_none = type(None) in (args if args else ())
        if has_none:
            schema["optional"] = True

        # Propagate inner generics
        if origin_name in ("list", "List") and args:
            inner = args[0]
            inner_origin = get_origin(inner)
            if inner_origin is not None and getattr(inner_origin, "__name__", "") in (
                "list",
                "List",
            ):
                schema["innerType"] = _type_to_port_type(get_args(inner)[0] if get_args(inner) else Any)
            else:
                schema["innerType"] = _type_to_port_type(inner)

        if origin_name in ("dict", "Dict") and args:
            schema["keyType"] = _type_to_port_type(args[0]) if len(args) > 0 else "str"
            schema["valueType"] = _type_to_port_type(args[1]) if len(args) > 1 else "Any"

    return schema


# ---------------------------------------------------------------------------
# Subclass discovery
# ---------------------------------------------------------------------------


def _concrete_action_subclasses() -> Set[Type[Action]]:
    """Recursively collect all concrete (non-abstract) Action subclasses."""
    concrete: Set[Type[Action]] = set()
    seen: Set[Type[Action]] = set()

    # Use a deque so we can process breadth-first; Action itself is abstract.
    queue: deque[Type[Action]] = deque(Action.__subclasses__())

    while queue:
        cls = queue.popleft()
        if cls in seen:
            continue
        seen.add(cls)

        # Concrete = instantiable and runnable: no abstract methods and the
        # resolved _execute is a real implementation (not the abstract base
        # stub).  The inherited case matters: generic bases like
        # StoreDocuments implement _execute once and parameterised subclasses
        # (StoreArticleEssence) reuse it without declaring their own.
        is_abstract = getattr(cls, "__abstractmethods__", None)
        is_abstract_class = bool(is_abstract)
        resolves_own_execute = cls._execute is not Action.__dict__["_execute"]
        # Generic aliases (e.g. RetrieveFromPersistent[TypeVar]) are not real
        # classes; their mangled __name__ gives them away.
        is_generic_alias = "[" in cls.__name__

        if not is_abstract_class and resolves_own_execute and not is_generic_alias:
            concrete.add(cls)

        queue.extend(cls.__subclasses__())

    return concrete


# ---------------------------------------------------------------------------
# Port extraction
# ---------------------------------------------------------------------------


def _mro_field_owner(cls: Type[Action], field_name: str) -> str:
    """Return the first class in *cls*'s MRO that declares *field_name*.

    Pydantic v2 keeps each class's declared annotations on its own
    ``__annotations__``, so walking the MRO leaf-first attributes a field to
    the most-derived class that declares it.  The result is the ``group``
    key used by the workflow UI to fold inherited (scoped-config) fields.
    Falls back to *cls* itself for fields injected without annotations.
    """
    for base in cls.__mro__:
        annotations = getattr(base, "__annotations__", None)
        if annotations and field_name in annotations:
            return base.__name__
    return cls.__name__


def _extract_input_ports(cls: Type[Action]) -> List[Dict[str, Any]]:
    """Extract input ports from *cls* model fields, excluding infrastructure fields."""
    ports: List[Dict[str, Any]] = []

    for field_name, field_info in cls.model_fields.items():
        if field_name in EXCLUDED_FIELDS:
            continue
        if field_name.startswith("_"):
            continue

        ann = field_info.annotation
        if ann is None:
            ann = str

        schema = _annotation_to_schema(ann)
        schema["name"] = field_name
        schema["label"] = field_info.title or field_name.replace("_", " ").title()

        desc = field_info.description
        if desc:
            schema["description"] = desc

        # Default value
        has_default = (
            field_info.default is not None
            and field_info.default is not ...
            and isinstance(field_info.default, (str, int, float, bool, type(None)))
        )
        if has_default:
            schema["default"] = field_info.default

        # Always set optional (required by Rust PortDefinition)
        schema.setdefault("optional", has_default)

        # Widget hint for the inline editor
        schema.update(_widget_hint(ann, has_default, field_info.default))

        # MRO owner class name — drives arg-grouping in the workflow UI
        schema["group"] = _mro_field_owner(cls, field_name)

        ports.append(schema)

    return ports


def _extract_output_ports(cls: Type[Action]) -> List[Dict[str, Any]]:
    """Extract output ports from *cls* — one port per output_key."""
    output_key: str = getattr(cls, "output_key", "") or cls.model_fields.get("output_key", FieldInfo()).default or ""
    if not output_key:
        output_key = cls.__name__.lower()

    return [
        {
            "name": output_key,
            "type": "Any",
            "optional": False,
            "description": f"Output from {cls.__name__}",
        }
    ]


def _extract_capabilities(cls: Type[Action]) -> List[str]:
    """Return capability marker strings from the MRO."""
    caps: List[str] = []

    for base in cls.__mro__:
        if base is Action or base is object:
            continue
        if issubclass(base, Action) and base is not Action and base is not cls:
            continue
        # Non-Action bases are capabilities
        if not issubclass(base, Action):
            caps.append(base.__name__)

    return sorted(set(caps))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


_ACTION_MODULE_CANDIDATES: List[str] = [
    "fabricatio_actions.actions",
    "fabricatio_actions.actions.output",
    "fabricatio_actions.actions.fs",
    "fabricatio_novel.actions.novel",
    "fabricatio_novel.actions.novel_mental",
    "fabricatio_novel.actions.novel_rag",
    "fabricatio_novel.actions.enrich",
    "fabricatio_novel.actions.illustration",
    "fabricatio_anki.actions",
    "fabricatio_typst.actions",
    "fabricatio_typst.actions.article",
    "fabricatio_typst.actions.article_rag",
    "fabricatio_comfyui.actions",
    "fabricatio_capabilities.actions",
    "fabricatio_improve.actions",
    "fabricatio_question.actions",
    "fabricatio_rule.actions",
]


def _discover_action_modules() -> None:
    """Try to import known action modules so __subclasses__() can find them."""
    for mod_name in _ACTION_MODULE_CANDIDATES:
        with contextlib.suppress(ImportError):
            __import__(mod_name)


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

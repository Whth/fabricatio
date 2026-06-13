"""Action introspection registry for the fabricatio-webui workflow editor.

Discovers all concrete Action subclasses and produces a node type registry
suitable for frontend rendering as a ComfyUI-style node palette.
"""

import contextlib
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Set, Type, Union, get_args, get_origin

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

        if origin_name == "Optional" or (origin is Union and len(args) == 2 and type(None) in args):
            inner = next(a for a in args if a is not type(None))
            inner_str = _type_to_port_type(inner)
            return f"{inner_str}?"

        if origin_name in ("list", "List"):
            if args:
                inner_str = _type_to_port_type(args[0])
                return f"List[{inner_str}]"
            return "List"

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

        # Check if it's concrete (has _execute defined differently from Action)
        has_own_execute = "_execute" in cls.__dict__ and cls.__dict__["_execute"] is not Action.__dict__["_execute"]

        # Also check if the class is not abstract (ABC check)
        is_abstract = getattr(cls, "__abstractmethods__", None)
        is_abstract_class = bool(is_abstract)

        if has_own_execute and not is_abstract_class:
            concrete.add(cls)

        queue.extend(cls.__subclasses__())

    return concrete


# ---------------------------------------------------------------------------
# Port extraction
# ---------------------------------------------------------------------------


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
    "fabricatio_novel.actions.illustration",
    "fabricatio_anki.actions",
    "fabricatio_typst.actions",
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

            entry: Dict[str, Any] = {
                "type": cls.__name__,
                "title": first_line or cls.__name__,
                "description": doc,
                "category": _derive_category(cls),
                "input_ports": _extract_input_ports(cls),
                "output_ports": _extract_output_ports(cls),
                "capabilities": _extract_capabilities(cls),
                "ctx_override": getattr(cls, "ctx_override", False),
                "config_fields": [],
            }
            node_types.append(entry)
        except Exception:  # noqa: BLE001
            logger.warn(f"Failed to introspect Action subclass {cls.__name__!r}; skipping.")

    return {
        "version": "1.0",
        "node_types": node_types,
    }

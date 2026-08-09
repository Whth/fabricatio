"""Port extraction from Action model fields and MRO capabilities."""

from typing import Any, Dict, List, Type

from fabricatio_core.models.action import Action
from pydantic.fields import FieldInfo

from fabricatio_webui.registry._constants import EXCLUDED_FIELDS
from fabricatio_webui.registry._schema import _annotation_to_schema, _widget_hint


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

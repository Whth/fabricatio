"""Port extraction from Action model fields and MRO capabilities."""

from fabricatio_core.models.action import Action
from pydantic.fields import FieldInfo

from fabricatio_webui.models.wire import PortSchema
from fabricatio_webui.registry._constants import EXCLUDED_FIELDS
from fabricatio_webui.registry._schema import _annotation_to_schema, _widget_hint


def _mro_field_owner(cls: type[Action], field_name: str) -> str:
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


def resolve_output_key(cls: type[Action], *, instance: Action | None = None, fallback: str = "") -> str:
    """The context key *cls*'s output is stored under.

    ``output_key`` when set (taken from *instance* when one is given, so a
    per-execution override wins), else the frozen field default, else the
    lowercased class name.  *fallback* is the last resort for callers that must
    never produce an empty key.  This is the single resolution chain shared by
    :mod:`._ports`, :mod:`fabricatio_webui.blueprints`, and
    :mod:`fabricatio_webui.executor`.
    """
    key = instance.output_key if instance is not None else getattr(cls, "output_key", "")
    return key or cls.model_fields.get("output_key", FieldInfo()).default or cls.__name__.lower() or fallback


def _extract_input_ports(cls: type[Action]) -> list[PortSchema]:
    """Extract input ports from *cls* model fields, excluding infrastructure fields."""
    ports: list[PortSchema] = []

    for field_name, field_info in cls.model_fields.items():
        if field_name in EXCLUDED_FIELDS:
            continue
        if field_name.startswith("_"):
            continue

        ann = field_info.annotation
        if ann is None:
            ann = str

        base = _annotation_to_schema(ann)

        # Default value (JSON-safe scalars only).
        has_default = (
            field_info.default is not None
            and field_info.default is not ...
            and isinstance(field_info.default, (str, int, float, bool, type(None)))
        )

        # Compose in the same order the previous setdefault/update sequence
        # produced: base -> name -> description -> default -> optional -> widget
        # hints -> group.  ``optional`` is only filled in when the annotation
        # did not already pin it (Optional[T] sets it upstream).
        port: PortSchema = {
            **base,
            "name": field_name,
            **({"description": field_info.description} if field_info.description else {}),
            **({"default": field_info.default} if has_default else {}),
            **({} if "optional" in base else {"optional": has_default}),
            **_widget_hint(ann, has_default, field_info.default),
            "group": _mro_field_owner(cls, field_name),
        }
        ports.append(port)

    return ports


def _extract_output_ports(cls: type[Action]) -> list[PortSchema]:
    """Extract output ports from *cls* — one port per output_key."""
    return [
        {
            "name": resolve_output_key(cls),
            "type": "Any",
            "optional": False,
            "description": f"Output from {cls.__name__}",
        },
    ]


def _extract_capabilities(cls: type[Action]) -> list[str]:
    """Return capability marker strings from the MRO."""
    caps: list[str] = []

    for base in cls.__mro__:
        if base is Action or base is object:
            continue
        if issubclass(base, Action) and base is not Action and base is not cls:
            continue
        # Non-Action bases are capabilities
        if not issubclass(base, Action):
            caps.append(base.__name__)

    return sorted(set(caps))

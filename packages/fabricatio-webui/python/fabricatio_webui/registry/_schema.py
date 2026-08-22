"""Type-annotation to frontend schema conversion."""

from pathlib import Path
from types import UnionType
from typing import Annotated, Any, Dict, Literal, Tuple, Union, get_args, get_origin

from pydantic.fields import FieldInfo


def _union_port_type(args: Tuple[Any, ...]) -> str:
    """Render a union's port type: a single member unwraps to ``T?``, multi stays wildcard."""
    non_none = [a for a in args if a is not type(None)]
    if len(non_none) == 1:
        return f"{_type_to_port_type(non_none[0])}?"
    if non_none:
        # Multi-member union (e.g. str | Path): the registry cannot
        # enumerate members — keep the wildcard so any output fits.
        return "Union"
    return "None"


def _plain_port_type(ann: Any) -> str:
    """Render a plain (non-generic) annotation's port type."""
    if isinstance(ann, type):
        if issubclass(ann, Path):
            return "Path"
        if hasattr(ann, "__name__"):
            return ann.__name__
    return str(ann)


def _type_to_port_type(ann: Any) -> str:  # noqa: PLR0911
    """Convert a Python type annotation into a frontend-friendly string."""
    origin = get_origin(ann)

    if origin is None:
        return _plain_port_type(ann)

    origin_name = getattr(origin, "__name__", str(origin))
    args = get_args(ann)

    if origin is type(None):
        return "None"
    if origin in (Union, UnionType) and args:
        return _union_port_type(args)
    if origin is Annotated and args:
        return _type_to_port_type(args[0])
    if origin_name in ("list", "List"):
        if args:
            return f"List[{_type_to_port_type(args[0])}]"
        return "List"
    if origin_name == "Literal":
        return "Literal"
    # generic aliases e.g. Task[T]
    return origin_name


def _widget_for_bare_type(ann: Any, has_default: bool, default: Any) -> Dict[str, Any] | None:
    """Widget hint for a bare (non-generic) annotation; ``None`` when unhandled."""
    if not isinstance(ann, type):
        return None
    # bool must be tested before int (it subclasses int).
    if issubclass(ann, bool):
        return {"widget": "toggle"}
    if issubclass(ann, (int, float)):
        step = 1 if issubclass(ann, int) else 0.1
        return {"widget": "number", "step": step}
    if issubclass(ann, Path):
        return {"widget": "text", "placeholder": "/path/to/file"}
    if issubclass(ann, str):
        long_default = has_default and isinstance(default, str) and len(default) > 120
        return {"widget": "textarea" if long_default else "text"}
    return None


def _widget_hint(ann: Any, has_default: bool, default: Any) -> Dict[str, Any]:
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
    # FieldInfo.metadata as annotated_types objects.
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

    # Bare-type mapping first; anything unresolvable falls back to JSON.
    return _widget_for_bare_type(ann, has_default, default) or {"widget": "json"}


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

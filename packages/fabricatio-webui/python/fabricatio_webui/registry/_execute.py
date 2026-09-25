"""Introspection of Action._execute signatures — the runtime dataflow surface."""

import inspect

from fabricatio_core.models.action import Action

from fabricatio_webui.registry._constants import _RUNTIME_PLUMBING


def _execute_signature(cls: type[Action]) -> inspect.Signature | None:
    """The resolved signature of *cls*._execute, or ``None`` when unavailable.

    Builtin/Rust-backed actions have no introspectable signature; every
    consumer treats that as "no dataflow parameters".
    """
    try:
        return inspect.signature(cls._execute)
    except (TypeError, ValueError):
        return None


def _execute_params(cls: type[Action]) -> list[str]:
    """Non-plumbing named parameters of *cls*._execute (no **kwargs)."""
    sig = _execute_signature(cls)
    if sig is None:
        return []
    return [
        name
        for name, param in sig.parameters.items()
        if name not in _RUNTIME_PLUMBING and param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY)
    ]


def _required_execute_params(cls: type[Action]) -> list[str]:
    """Non-plumbing _execute parameters without a default value."""
    sig = _execute_signature(cls)
    if sig is None:
        return []
    return [
        name
        for name, param in sig.parameters.items()
        if name not in _RUNTIME_PLUMBING
        and param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY)
        and param.default is param.empty
    ]


def _consumes_context(cls: type[Action]) -> bool:
    """True when *cls*._execute receives the whole workflow context.

    Either via a ``**kwargs`` catch-all (novel actions take ``**cxt``) or a
    named context parameter.  Such steps are dataflow-connected to every
    predecessor through the shared context even without a field match.
    """
    sig = _execute_signature(cls)
    if sig is None:
        return False
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()) or any(
        name in {"cxt", "ctx", "context"} for name in sig.parameters
    )

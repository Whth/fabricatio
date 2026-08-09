"""Introspection of Action._execute signatures — the runtime dataflow surface."""

import inspect
from typing import List, Type

from fabricatio_core.models.action import Action

from fabricatio_webui.registry._constants import _RUNTIME_PLUMBING


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

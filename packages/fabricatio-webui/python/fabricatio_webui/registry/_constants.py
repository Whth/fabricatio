"""Registry constants — fields excluded from node input ports."""

from typing import Set

try:
    from fabricatio_core.models.role import EXCLUDED_FIELDS as _ROLE_EXCLUDED
except ImportError:
    _ROLE_EXCLUDED = None

_HARD_EXCLUDED: Set[str] = {"name", "description", "output_key", "ctx_override"}

if _ROLE_EXCLUDED is not None:
    EXCLUDED_FIELDS: Set[str] = _HARD_EXCLUDED | _ROLE_EXCLUDED
else:
    EXCLUDED_FIELDS = _HARD_EXCLUDED

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

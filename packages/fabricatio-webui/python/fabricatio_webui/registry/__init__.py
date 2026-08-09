"""Action introspection registry for the fabricatio-webui workflow editor.

Discovers all concrete Action subclasses and produces a node type registry
suitable for frontend rendering as a ComfyUI-style node palette.

Implementation split by concern:

- :mod:`._constants` — excluded fields and plumbing parameter names
- :mod:`._execute`   — ``_execute`` signature introspection (dataflow ports)
- :mod:`._category`  — node-palette category derivation from the MRO
- :mod:`._schema`    — type-annotation → frontend schema conversion
- :mod:`._ports`     — input/output port and capability extraction
- :mod:`._discover`  — Action subclass discovery
- :mod:`._build`     — registry build + document migration
"""

from fabricatio_webui.registry._build import (
    _worker_registry,
    build_node_registry,
    migrate_board,
    migrate_workflow,
)
from fabricatio_webui.registry._category import _derive_category, _mro_class_names
from fabricatio_webui.registry._constants import _RUNTIME_PLUMBING, CONTEXT_PORT_NAME, EXCLUDED_FIELDS
from fabricatio_webui.registry._discover import (
    _ACTION_MODULE_CANDIDATES,
    _concrete_action_subclasses,
    _discover_action_modules,
)
from fabricatio_webui.registry._execute import _consumes_context, _execute_params, _required_execute_params
from fabricatio_webui.registry._ports import (
    _extract_capabilities,
    _extract_input_ports,
    _extract_output_ports,
    _mro_field_owner,
)
from fabricatio_webui.registry._schema import (
    _annotation_to_schema,
    _apply_number_constraints,
    _type_to_port_type,
    _widget_hint,
)

__all__ = [
    "CONTEXT_PORT_NAME",
    "EXCLUDED_FIELDS",
    "_ACTION_MODULE_CANDIDATES",
    "_RUNTIME_PLUMBING",
    "_annotation_to_schema",
    "_apply_number_constraints",
    "_concrete_action_subclasses",
    "_consumes_context",
    "_derive_category",
    "_discover_action_modules",
    "_execute_params",
    "_extract_capabilities",
    "_extract_input_ports",
    "_extract_output_ports",
    "_mro_class_names",
    "_mro_field_owner",
    "_required_execute_params",
    "_type_to_port_type",
    "_widget_hint",
    "_worker_registry",
    "build_node_registry",
    "migrate_board",
    "migrate_workflow",
]

"""Typed wire vocabulary shared by the webui worker, executor, and registry.

Every model here mirrors a shape that crosses the Rust/Python boundary (or a
persisted JSON document). Field names are the wire names verbatim, so the
models double as the serialization contract with ``src/types.rs``.
"""

from enum import StrEnum, auto
from types import GenericAlias, UnionType
from typing import NamedTuple, TypedDict

#: The JSON data domain serialized to Rust (``serde_json::Value``). Recursive
#: on purpose: node outputs, task results, and history payloads are arbitrary
#: JSON trees.
type JSONValue = str | int | float | bool | list[JSONValue] | dict[str, JSONValue] | None

#: A Python type annotation (a bare class such as ``str``/``Path``, a PEP 604
#: union, a parameterised generic such as ``list[str]``, or a forward-ref
#: string). The registry's schema converters accept any ``typing`` construct;
#: this alias names the public subset they can be handed.
type TypeAnnotation = type | GenericAlias | UnionType | str


class ExecState(StrEnum):
    """Execution lifecycle state as serialized on the wire (snake_case).

    ``StrEnum.auto()`` yields the lowercased member name, so members
    serialize exactly to the wire strings.
    """

    QUEUED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    CANCELLED = auto()
    FAILED = auto()


class PortSchema(TypedDict, total=False):
    """One input/output/config port as emitted by the registry and read by Rust.

    ``total=False`` because the shape is assembled incrementally: only ``type``
    is always present, and widget hints / defaults / group appear conditionally.
    """

    name: str
    type: str
    optional: bool
    description: str
    widget: str
    options: list[str]
    default: JSONValue
    min: float
    max: float
    step: float
    placeholder: str
    separator: str
    group: str


class NodeRegistryEntry(TypedDict):
    """One node type descriptor produced by ``build_node_registry()``."""

    type: str
    title: str
    description: str
    category: str
    input_ports: list[PortSchema]
    output_ports: list[PortSchema]
    capabilities: list[str]
    ctx_override: bool
    config_fields: list[PortSchema]
    module: str
    source_code: str
    schema_version: str


class NodeRegistry(TypedDict):
    """The versioned node-type registry document."""

    version: str
    registry_version: str
    node_types: list[NodeRegistryEntry]


class HistoryRecord(TypedDict):
    """One ``ExecutionStatus`` row in ``WorkflowWorker.history_snapshot()``."""

    execution_id: str
    state: ExecState
    current_node: str | None
    error: str | None
    result: JSONValue
    task_name: str
    namespace: str


class QueueEntry(TypedDict):
    """One row of ``WorkflowWorker.queue_snapshot()`` (queued or active)."""

    execution_id: str
    state: ExecState


class Submission(NamedTuple):
    """A queued task submission — the worker's queue item."""

    execution_id: str
    task_json: str


# ---------------------------------------------------------------------------
# WebSocket event payloads (broadcast server -> client)
# ---------------------------------------------------------------------------


class ExecutionStartPayload(TypedDict):
    """Payload of an ``execution_start`` frame (``timestamp`` filled by Rust)."""

    execution_id: str
    timestamp: str | None


class NodeStartPayload(TypedDict):
    """Payload of a ``node_start`` frame."""

    node_id: str
    node_type: str


class NodeDonePayload(TypedDict):
    """Payload of a ``node_done`` / ``node_output`` frame."""

    node_id: str
    node_type: str
    output_key: str
    output: str


class NodeErrorPayload(TypedDict):
    """Payload of a ``node_error`` frame."""

    node_id: str
    node_type: str
    error: str


class ExecutionDonePayload(TypedDict):
    """Payload of an ``execution_done`` frame."""

    execution_id: str
    cancelled: bool
    result: JSONValue
    error: str | None


class StatusPayload(TypedDict):
    """Payload of a ``status`` frame."""

    queue_length: int
    running_count: int

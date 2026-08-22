"""Core graph primitives and the :class:`WorkflowCore` graph container.

This module owns the *immutable* parts of a ComfyUI workflow graph:

* :class:`FrameAspect` — typed enum of ``ResolutionSelector`` aspect tokens.
* :class:`NodeRef` — typed ``[node_id, output_index]`` link between nodes.
* :class:`Node` — a single workflow node with typed input manipulation.
* :class:`WorkflowCore` — the concrete graph container: construction,
  CRUD, and serialization.  Domain-specific convenience setters
  (``set_sampler``, ``set_positive_prompt``, …) live in
  :mod:`fabricatio_comfyui.models.workflow_ops` and are composed into the
  final :class:`Workflow` via nominal multiple inheritance.

PEP 695 ``type`` aliases pin down the dict shapes that ComfyUI's API format
requires, so callers stop sprinkling ``dict[str, Any]`` everywhere.
"""

import json
from dataclasses import dataclass, field
from enum import StrEnum
from math import sqrt
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "RESOLUTION_SELECTOR_ASPECT_RATIOS",
    "FrameAspect",
    "Node",
    "NodeApi",
    "NodeInputs",
    "NodeRef",
    "WorkflowCore",
    "WorkflowDict",
]

# ------------------------------------------------------------------
# PEP 695 type aliases — the dict shapes ComfyUI's API format requires
# ------------------------------------------------------------------

type NodeInputs = dict[str, Any]
"""Per-node input map.  Values are literals OR ``[node_id, output_index]`` refs."""

type NodeApi = dict[str, Any]
"""Per-node API dict: ``{"class_type": str, "inputs": NodeInputs, "_meta"?: …}``."""

type WorkflowDict = dict[str, NodeApi]
"""Full ComfyUI API-format workflow graph: ``node_id -> NodeApi``."""


# ------------------------------------------------------------------
# FrameAspect — typed enum of ComfyUI ResolutionSelector aspect tokens
# ------------------------------------------------------------------


class FrameAspect(StrEnum):
    """Verbatim ComfyUI ``ResolutionSelector`` aspect-ratio tokens.

    Each member's value is the exact string ComfyUI's ``ResolutionSelector``
    custom node expects on the ``aspect_ratio`` input.  Each member also
    exposes its numeric (width, height) ratio via :attr:`ratio`, used by the
    literal-dimension fallback path (workflows without a
    ``ResolutionSelector`` node).

    :data:`RESOLUTION_SELECTOR_ASPECT_RATIOS` is *derived* from the member
    values, so the token set and the enum cannot drift apart.
    """

    SQUARE = "1:1 (Square)"
    PORTRAIT_PHOTO = "2:3 (Portrait Photo)"
    PHOTO = "3:2 (Photo)"
    PORTRAIT_STANDARD = "3:4 (Portrait Standard)"
    STANDARD = "4:3 (Standard)"
    WIDESCREEN_PORTRAIT = "9:16 (Portrait Widescreen)"
    WIDESCREEN = "16:9 (Widescreen)"
    ULTRAWIDE = "21:9 (Ultrawide)"

    @property
    def ratio(self) -> tuple[int, int]:
        """Numeric (width, height) ratio for this aspect token.

        Parsed straight from the member value (``"16:9 (Widescreen)"`` ->
        ``(16, 9)``), so the numeric ratio can never drift from the token
        ComfyUI receives.  Used to derive literal pixel dimensions from a
        target megapixel count for workflows that drive
        ``EmptyLatentImage.width/height`` directly rather than through a
        ``ResolutionSelector`` node.
        """
        width_token, height_token = self.value.split(" ", 1)[0].split(":")
        return int(width_token), int(height_token)

    def to_dimensions(self, megapixels: float) -> tuple[int, int]:
        """Return aligned literal pixel dimensions for ``megapixels``.

        Derives width and height from this member's hard-coded ratio, rounds
        both dimensions to ComfyUI's 8-pixel alignment, and enforces a
        64-pixel minimum on each axis.
        """
        ratio_width, ratio_height = self.ratio
        height = sqrt(megapixels * 1_000_000 * ratio_height / ratio_width)
        width = height * ratio_width / ratio_height
        width_rounded = round(width / 8) * 8
        height_rounded = round(height / 8) * 8
        return max(64, width_rounded), max(64, height_rounded)


RESOLUTION_SELECTOR_ASPECT_RATIOS: frozenset[str] = frozenset(member.value for member in FrameAspect)
"""The exact aspect-ratio token set the ``ResolutionSelector`` node accepts (derived from :class:`FrameAspect`)."""


# ------------------------------------------------------------------
# Node reference — typed link between nodes
# ------------------------------------------------------------------


class NodeRef(BaseModel):
    """A typed reference to another node's output.

    In the ComfyUI API format, connections are stored as ``[node_id, output_index]``.
    This model makes that explicit.
    """

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    node_id: str
    """The source node ID."""

    output_index: int = 0
    """The output index on the source node (default 0)."""

    def to_api(self) -> list[str | int]:
        """Serialize to ComfyUI API format: ``[node_id, output_index]``."""
        return [self.node_id, self.output_index]

    @classmethod
    def from_api(cls, raw: list[Any]) -> Self:
        """Parse from ``[node_id, output_index]``."""
        return cls(node_id=str(raw[0]), output_index=int(raw[1]))

    @staticmethod
    def is_ref(value: Any) -> bool:
        """Return ``True`` if *value* looks like a node reference."""
        return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)


# ------------------------------------------------------------------
# Single node
# ------------------------------------------------------------------


class Node(BaseModel):
    """A single node in a ComfyUI workflow graph.

    Inputs are stored in their API-format representation.  Literal values
    keep their native types.  Node connections are stored as
    ``[node_id, output_index]`` lists — use :meth:`connect` /
    :meth:`get_ref` for typed access.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)

    id: str
    """Node identifier (e.g. ``"42"``)."""

    type: str
    """ComfyUI node class (e.g. ``"KSampler"``, ``"CLIPTextEncode"``)."""

    inputs: NodeInputs = Field(default_factory=dict)
    """Input values.  Literals are native types; node refs are ``[node_id, output_index]``."""

    title: str = ""
    """Human-readable title (stored in ``_meta.title``)."""

    # ------------------------------------------------------------------
    # Input manipulation
    # ------------------------------------------------------------------

    def set_input(self, name: str, value: Any) -> Self:
        """Set a literal input value."""
        self.inputs[name] = value
        return self

    def connect(self, input_name: str, source: "Node", output_index: int = 0) -> Self:
        """Wire *input_name* to *source*'s output at *output_index*."""
        self.inputs[input_name] = [source.id, output_index]
        return self

    def get_ref(self, input_name: str) -> NodeRef | None:
        """Return a :class:`NodeRef` if the input is a connection, else ``None``."""
        val = self.inputs.get(input_name)
        if NodeRef.is_ref(val):
            return NodeRef.from_api(val)
        return None

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_api(self) -> NodeApi:
        """Serialize to ComfyUI API format."""
        d: NodeApi = {
            "inputs": dict(self.inputs),
            "class_type": self.type,
        }
        if self.title:
            d["_meta"] = {"title": self.title}
        return d

    def __repr__(self) -> str:
        """Return a developer-friendly representation of this node."""
        label = f" ({self.title})" if self.title else ""
        return f"Node({self.id!r}, {self.type!r}{label})"


# ------------------------------------------------------------------
# WorkflowCore — abstract graph container (construction + CRUD + ser/de)
# ------------------------------------------------------------------


@dataclass
class WorkflowCore:
    """ComfyUI workflow graph container.

    Owns the node map, ID counter, construction (``from_api`` /
    ``from_file`` / ``default``), CRUD (``add`` / ``get`` / ``by_type`` /
    ``remove``), and serialization (``to_api``).  Domain-specific setters
    are deliberately absent — they live on the ``*Ops`` ABCs in
    :mod:`fabricatio_comfyui.models.workflow_ops` and are mixed into the
    concrete :class:`fabricatio_comfyui.models.workflow.Workflow`.

    This class is fully concrete; the composed ``Workflow`` is the intended
    entry point.  The ``*Ops`` mixins declare their dependency on
    :class:`WorkflowAccess`'s abstract helpers, which ``WorkflowCore``
    satisfies with concrete implementations.
    """

    node_map: dict[str, Node] = field(default_factory=dict)
    counter: int = 1

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def new(cls) -> Self:
        """Create an empty workflow."""
        return cls()

    @classmethod
    def from_api(cls, data: WorkflowDict) -> Self:
        """Load from a ComfyUI API-format JSON dict."""
        wf = cls()
        max_id = 0
        for node_id, node_data in data.items():
            nid = int(node_id)
            max_id = max(max_id, nid)
            meta = node_data.get("_meta", {})
            wf.node_map[node_id] = Node(
                id=node_id,
                type=node_data.get("class_type", ""),
                inputs=dict(node_data.get("inputs", {})),
                title=meta.get("title", ""),
            )
        wf.counter = max_id + 1
        return wf

    @classmethod
    def from_file(cls, path: str | Path) -> Self:
        """Load from a ``.json`` file."""
        p = Path(path)
        return cls.from_api(json.loads(p.read_text(encoding="utf-8")))

    @classmethod
    def default(cls) -> Self:
        """Load the bundled demo workflow shipped with the package."""
        demo = Path(__file__).resolve().parent.parent / "workflows" / "default.json"
        return cls.from_file(demo)

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    def add(
        self,
        type: str,
        *,
        title: str = "",
        inputs: NodeInputs | None = None,
    ) -> Node:
        """Add a new node, auto-assigning the next available ID."""
        node_id = str(self.counter)
        self.counter += 1
        node = Node(id=node_id, type=type, inputs=dict(inputs) if inputs else {}, title=title)
        self.node_map[node_id] = node
        return node

    def get(self, node_id: str) -> Node:
        """Get a node by ID.  Raises ``KeyError`` if not found."""
        return self.node_map[node_id]

    def by_type(self, type: str) -> list[Node]:
        """Find all nodes with the given *type*."""
        return [n for n in self.node_map.values() if n.type == type]

    def remove(self, node_id: str) -> None:
        """Remove a node and disconnect all references to it."""
        del self.node_map[node_id]
        for node in self.node_map.values():
            to_remove = [k for k, v in node.inputs.items() if NodeRef.is_ref(v) and v[0] == node_id]
            for k in to_remove:
                del node.inputs[k]

    @property
    def node_ids(self) -> list[str]:
        """All node IDs in this workflow."""
        return list(self.node_map.keys())

    @property
    def nodes(self) -> list[Node]:
        """All nodes in this workflow."""
        return list(self.node_map.values())

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_api(self) -> WorkflowDict:
        """Serialize to ComfyUI API format (pass to ``client.queue_prompt``)."""
        return {node_id: node.to_api() for node_id, node in self.node_map.items()}

    # ------------------------------------------------------------------
    # Internal resolver — shared by every *Ops mixin
    # ------------------------------------------------------------------

    def _resolve(self, type: str, node_id: str | None) -> Node:
        """Return the node for *type* (first match) or the explicit *node_id*."""
        if node_id is not None:
            node = self.node_map.get(node_id)
            if node is None:
                raise KeyError(f"Node {node_id!r} not found")
            return node
        matches = self.by_type(type)
        if not matches:
            raise KeyError(f"No node with type={type!r} found in workflow")
        return matches[0]

    def _require_node(self, node_id: str) -> Node:
        """Return the node for *node_id* or raise ``KeyError``."""
        node = self.node_map.get(node_id)
        if node is None:
            raise KeyError(f"Node {node_id!r} not found")
        return node

    def __repr__(self) -> str:
        """Return a developer-friendly representation of this workflow."""
        return f"{type(self).__name__}({len(self.node_map)} nodes)"

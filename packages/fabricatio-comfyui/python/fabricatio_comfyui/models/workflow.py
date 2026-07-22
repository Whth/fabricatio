"""Typed models for ComfyUI workflow graphs.

Provides :class:`Node` (a single workflow node) and :class:`Workflow`
(a full workflow graph) with proper typing, validation, and clean
API-format serialization.
"""

import json
from dataclasses import dataclass, field
from enum import StrEnum
from math import sqrt
from pathlib import Path
from typing import Any, Dict, List, Self, Tuple

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["RESOLUTION_SELECTOR_ASPECT_RATIOS", "FrameAspect", "Node", "NodeRef", "Workflow"]

from fabricatio_core.utils import ok

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

    Values are kept in lockstep with :data:`RESOLUTION_SELECTOR_ASPECT_RATIOS`
    via the module-level ``assert`` below; edits to one without the other will
    raise ``AssertionError`` at import.
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
    def ratio(self) -> Tuple[int, int]:
        """Numeric (width, height) ratio for this aspect token.

        Used to derive literal pixel dimensions from a target megapixel count
        for workflows that drive ``EmptyLatentImage.width/height`` directly
        rather than through a ``ResolutionSelector`` node.
        """
        ratio: Tuple[int, int] | None = None
        match self:
            case FrameAspect.SQUARE:
                ratio = (1, 1)
            case FrameAspect.PHOTO:
                ratio = (3, 2)
            case FrameAspect.PORTRAIT_PHOTO:
                ratio = (2, 3)
            case FrameAspect.PORTRAIT_STANDARD:
                ratio = (3, 4)
            case FrameAspect.STANDARD:
                ratio = (4, 3)
            case FrameAspect.WIDESCREEN_PORTRAIT:
                ratio = (9, 16)
            case FrameAspect.WIDESCREEN:
                ratio = (16, 9)
            case FrameAspect.ULTRAWIDE:
                ratio = (21, 9)

        return ok(ratio)

    def to_dimensions(self, megapixels: float) -> Tuple[int, int]:
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


RESOLUTION_SELECTOR_ASPECT_RATIOS: frozenset[str] = frozenset(
    {
        FrameAspect.SQUARE,
        FrameAspect.PORTRAIT_PHOTO,
        FrameAspect.PHOTO,
        FrameAspect.PORTRAIT_STANDARD,
        FrameAspect.STANDARD,
        FrameAspect.WIDESCREEN_PORTRAIT,
        FrameAspect.WIDESCREEN,
        FrameAspect.ULTRAWIDE,
    }
)
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

    inputs: Dict[str, Any] = Field(default_factory=dict)
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

    def to_api(self) -> Dict[str, Any]:
        """Serialize to ComfyUI API format."""
        d: Dict[str, Any] = {
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
# Full workflow graph
# ------------------------------------------------------------------


@dataclass
class Workflow:
    """Programmatic builder for ComfyUI workflow graphs.

    Load from exported API-format JSON or build from scratch::

        wf = Workflow.from_file("demo.json")
        wf.set_positive_prompt("masterpiece, best quality")
        wf.set_checkpoint("v1-5-pruned-emaonly.safetensors")

        # Serialize for client.queue_prompt()
        data = wf.to_api()

        # Build from scratch
        wf = Workflow.new()
        ckpt = wf.add("CheckpointLoaderSimple", inputs={"ckpt_name": "model.safetensors"})
        empty = wf.add("EmptyLatentImage", inputs={"width": 512, "height": 512, "batch_size": 1})
        pos = wf.add("CLIPTextEncode", inputs={"text": "a cat"})
        pos.connect("clip", ckpt, 1)
    """

    node_map: Dict[str, Node] = field(default_factory=dict)
    counter: int = 1

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def new(cls) -> Self:
        """Create an empty workflow."""
        return cls()

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> Self:
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
        inputs: Dict[str, Any] | None = None,
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

    def by_type(self, type: str) -> List[Node]:
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

    def to_api(self) -> Dict[str, Any]:
        """Serialize to ComfyUI API format (pass to ``client.queue_prompt``)."""
        return {node_id: node.to_api() for node_id, node in self.node_map.items()}

    # ------------------------------------------------------------------
    # Convenience methods for common operations
    # ------------------------------------------------------------------

    def set_checkpoint(self, ckpt_name: str, *, node_id: str | None = None) -> Node:
        """Set the checkpoint on a ``CheckpointLoaderSimple`` node."""
        node = self._resolve("CheckpointLoaderSimple", node_id)
        node.set_input("ckpt_name", ckpt_name)
        return node

    def set_vae(self, vae_name: str, *, node_id: str | None = None) -> Node:
        """Set the VAE on a ``VAELoader`` node."""
        node = self._resolve("VAELoader", node_id)
        node.set_input("vae_name", vae_name)
        return node

    def set_positive_prompt(self, text: str, *, node_id: str | None = None) -> Node:
        """Set the positive prompt text on a ``CLIPTextEncode`` node."""
        return self._set_prompt(text, node_id, index=0)

    def set_negative_prompt(self, text: str, *, node_id: str | None = None) -> Node:
        """Set the negative prompt text on a ``CLIPTextEncode`` node (second one)."""
        return self._set_prompt(text, node_id, index=1)

    def set_sampler(
        self,
        *,
        seed: int | None = None,
        steps: int | None = None,
        cfg: float | None = None,
        sampler_name: str | None = None,
        scheduler: str | None = None,
        denoise: float | None = None,
        node_id: str | None = None,
    ) -> Node:
        """Update sampler parameters on a ``KSampler`` or ``KSamplerAdvanced`` node."""
        node = self._find_sampler(node_id)
        if seed is not None:
            if "noise_seed" in node.inputs:
                node.set_input("noise_seed", seed)
            else:
                node.set_input("seed", seed)
        if steps is not None:
            node.set_input("steps", steps)
        if cfg is not None:
            node.set_input("cfg", cfg)
        if sampler_name is not None:
            node.set_input("sampler_name", sampler_name)
        if scheduler is not None:
            node.set_input("scheduler", scheduler)
        if denoise is not None:
            node.set_input("denoise", denoise)
        return node

    def set_resolution(
        self,
        *,
        width: int | None = None,
        height: int | None = None,
        node_id: str | None = None,
    ) -> Node:
        """Set width/height on an ``EmptyLatentImage`` node."""
        node = self._resolve("EmptyLatentImage", node_id)
        if width is not None:
            node.set_input("width", width)
        if height is not None:
            node.set_input("height", height)
        return node

    def set_chart_proportion(
        self,
        *,
        aspect_ratio: str | None = None,
        megapixels: float | None = None,
        multiple: int | None = None,
        node_id: str | None = None,
    ) -> Node:
        """Set the chart proportion on a ``ResolutionSelector`` node.

        Updates the ``aspect_ratio``, ``megapixels``, and/or ``multiple`` inputs
        on a :class:`Workflow`'s ``ResolutionSelector`` node.  Only the parameters
        that are provided (not ``None``) get written — pass ``None`` to leave the
        current value unchanged.

        If no ``ResolutionSelector`` exists in the workflow, raises :class:`KeyError`
        with a message pointing to :meth:`set_resolution` for literal dimension mode.

        Args:
            aspect_ratio: ComfyUI aspect ratio string, e.g. ``"16:9 (Widescreen)"``.
                Must be one of :data:`RESOLUTION_SELECTOR_ASPECT_RATIOS`.
            megapixels: Target megapixels e.g. ``1.7`` (float).
            multiple: Multiple constraint e.g. ``12`` (pixel alignment).
            node_id: Explicit node ID.  If omitted, uses the first ``ResolutionSelector``.

        Returns:
            The matched :class:`Node`.

        Raises:
            KeyError: If no ``ResolutionSelector`` node exists and no *node_id* is given,
                or *node_id* does not exist.
            ValueError: If *aspect_ratio* is not in :data:`RESOLUTION_SELECTOR_ASPECT_RATIOS`.
        """
        if node_id is not None:
            node = self.node_map.get(node_id)
            if node is None:
                raise KeyError(f"Node {node_id!r} not found")
            if node.type != "ResolutionSelector":
                raise KeyError(f"Node {node_id!r} is {node.type!r}, not ResolutionSelector")
        else:
            matches = self.by_type("ResolutionSelector")
            if not matches:
                raise KeyError(
                    "No ResolutionSelector node found in workflow. "
                    "Use set_resolution() for literal dimensions, or add a ResolutionSelector node."
                )
            node = matches[0]

        if aspect_ratio is not None and aspect_ratio not in RESOLUTION_SELECTOR_ASPECT_RATIOS:
            valid = ", ".join(sorted(RESOLUTION_SELECTOR_ASPECT_RATIOS, key=lambda s: float(s.split(":")[0])))
            raise ValueError(
                f"Invalid aspect_ratio {aspect_ratio!r}. Valid values for the current ResolutionSelector: {valid}."
            )

        if aspect_ratio is not None:
            node.set_input("aspect_ratio", aspect_ratio)
        if megapixels is not None:
            node.set_input("megapixels", megapixels)
        if multiple is not None:
            node.set_input("multiple", multiple)
        return node

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, type: str, node_id: str | None) -> Node:
        if node_id is not None:
            node = self.node_map.get(node_id)
            if node is None:
                raise KeyError(f"Node {node_id!r} not found")
            return node
        matches = self.by_type(type)
        if not matches:
            raise KeyError(f"No node with type={type!r} found in workflow")
        return matches[0]

    def _set_prompt(self, text: str, node_id: str | None, *, index: int) -> Node:
        if node_id is not None:
            node = self.node_map.get(node_id)
            if node is None:
                raise KeyError(f"Node {node_id!r} not found")
        else:
            matches = self.by_type("CLIPTextEncode")
            if len(matches) <= index:
                raise KeyError(f"Need at least {index + 1} CLIPTextEncode node(s), found {len(matches)}")
            node = matches[index]
        node.set_input("text", text)
        return node

    def _find_sampler(self, node_id: str | None) -> Node:
        if node_id is not None:
            node = self.node_map.get(node_id)
            if node is None:
                raise KeyError(f"Node {node_id!r} not found")
            return node
        for sampler_type in ("KSamplerAdvanced", "KSampler"):
            matches = self.by_type(sampler_type)
            if matches:
                return matches[0]
        raise KeyError("No KSampler or KSamplerAdvanced node found in workflow")

    def __repr__(self) -> str:
        """Return a developer-friendly representation of this workflow."""
        return f"Workflow({len(self.node_map)} nodes)"

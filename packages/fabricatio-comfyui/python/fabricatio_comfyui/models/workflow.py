"""Programmatic builder for ComfyUI workflow graphs.

Load workflows from exported API-format JSON (like ``demo.json``) or build
them from scratch, then modify nodes and connections without hand-editing JSON.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Self

__all__ = ["ComfyNode", "WorkflowBuilder"]


class ComfyNode:
    """A single node in a ComfyUI workflow graph.

    Attributes:
        node_id: String node identifier (e.g. ``"42"``).
        class_type: ComfyUI node class (e.g. ``"KSampler"``).
        inputs: Raw input values.  Node references are stored as ``[node_id, output_index]``.
        meta: The ``_meta`` dict (title, etc.).
    """

    __slots__ = ("class_type", "inputs", "meta", "node_id")

    def __init__(
        self,
        node_id: str,
        class_type: str,
        inputs: Dict[str, Any] | None = None,
        meta: Dict[str, str] | None = None,
    ) -> None:
        """Initialize a ComfyNode with its ID, type, inputs, and metadata."""
        self.node_id = node_id
        self.class_type = class_type
        self.inputs: Dict[str, Any] = dict(inputs) if inputs else {}
        self.meta: Dict[str, str] = dict(meta) if meta else {}

    # ------------------------------------------------------------------
    # Input manipulation
    # ------------------------------------------------------------------

    def set_input(self, name: str, value: Any) -> Self:
        """Set a literal input value."""
        self.inputs[name] = value
        return self

    def connect(self, input_name: str, source: ComfyNode, output_index: int = 0) -> Self:
        """Wire *input_name* to *source*'s output at *output_index*."""
        self.inputs[input_name] = [source.node_id, output_index]
        return self

    def get_ref(self, input_name: str) -> tuple[str, int] | None:
        """Return ``(node_id, output_index)`` if the input is a node reference, else ``None``."""
        val = self.inputs.get(input_name)
        if isinstance(val, (list, tuple)) and len(val) == 2 and isinstance(val[0], str):
            return (val[0], int(val[1]))
        return None

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to ComfyUI API format."""
        d: Dict[str, Any] = {
            "inputs": dict(self.inputs),
            "class_type": self.class_type,
        }
        if self.meta:
            d["_meta"] = dict(self.meta)
        return d

    def __repr__(self) -> str:
        """Return a developer-friendly string representation."""
        title = self.meta.get("title", "")
        label = f" ({title})" if title else ""
        return f"ComfyNode({self.node_id!r}, {self.class_type!r}{label})"


class WorkflowBuilder:
    """Programmatic builder for ComfyUI workflow graphs.

    Examples::

        # Load from an exported API-format JSON
        wb = WorkflowBuilder.from_file("demo.json")

        # Modify the checkpoint
        wb.set_checkpoint("v1-5-pruned-emaonly.safetensors")

        # Update the positive prompt
        wb.set_positive_prompt("masterpiece, best quality, 1girl")

        # Serialize back to a dict for queue_prompt()
        workflow_dict = wb.to_dict()

        # Build from scratch
        wb = WorkflowBuilder()
        ckpt = wb.add_node("CheckpointLoaderSimple", inputs={"ckpt_name": "model.safetensors"})
        empty = wb.add_node("EmptyLatentImage", inputs={"width": 512, "height": 512, "batch_size": 1})
        pos = wb.add_node("CLIPTextEncode", inputs={"text": "a cat"})
        pos.connect("clip", ckpt, 1)
        ...
    """

    __slots__ = ("_next_id", "_nodes")

    def __init__(self) -> None:
        """Initialize an empty workflow builder."""
        self._nodes: Dict[str, ComfyNode] = {}
        self._next_id: int = 1

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> Self:
        """Load from an exported ComfyUI API-format JSON dict.

        Node IDs and all input references are preserved exactly.
        """
        wb = cls()
        max_id = 0
        for node_id, node_data in data.items():
            nid = int(node_id)
            max_id = max(max_id, nid)
            wb._nodes[node_id] = ComfyNode(
                node_id=node_id,
                class_type=node_data.get("class_type", ""),
                inputs=dict(node_data.get("inputs", {})),
                meta=dict(node_data.get("_meta", {})),
            )
        wb._next_id = max_id + 1
        return wb

    @classmethod
    def from_file(cls, path: str | Path) -> Self:
        """Load from a ``.json`` file."""
        import json

        p = Path(path)
        return cls.from_json(json.loads(p.read_text(encoding="utf-8")))

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    def add_node(
        self,
        class_type: str,
        *,
        title: str = "",
        inputs: Dict[str, Any] | None = None,
    ) -> ComfyNode:
        """Add a new node, auto-assigning the next available ID."""
        node_id = str(self._next_id)
        self._next_id += 1
        meta: Dict[str, str] = {}
        if title:
            meta["title"] = title
        node = ComfyNode(node_id=node_id, class_type=class_type, inputs=inputs, meta=meta)
        self._nodes[node_id] = node
        return node

    def get_node(self, node_id: str) -> ComfyNode:
        """Get a node by ID.  Raises ``KeyError`` if not found."""
        return self._nodes[node_id]

    def nodes_by_type(self, class_type: str) -> List[ComfyNode]:
        """Find all nodes with the given *class_type*."""
        return [n for n in self._nodes.values() if n.class_type == class_type]

    def remove_node(self, node_id: str) -> None:
        """Remove a node and disconnect all references to it from other nodes."""
        del self._nodes[node_id]
        for node in self._nodes.values():
            to_remove = []
            for key, val in node.inputs.items():
                if isinstance(val, (list, tuple)) and len(val) == 2 and val[0] == node_id:
                    to_remove.append(key)
            for key in to_remove:
                del node.inputs[key]

    @property
    def node_ids(self) -> list[str]:
        """All node IDs in this workflow."""
        return list(self._nodes.keys())

    @property
    def nodes(self) -> list[ComfyNode]:
        """All nodes in this workflow."""
        return list(self._nodes.values())

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to ComfyUI API format (pass to ``client.queue_prompt``)."""
        return {node_id: node.to_dict() for node_id, node in self._nodes.items()}

    # ------------------------------------------------------------------
    # Convenience methods for common operations
    # ------------------------------------------------------------------

    def set_checkpoint(self, ckpt_name: str, *, node_id: str | None = None) -> ComfyNode:
        """Set the checkpoint on a ``CheckpointLoaderSimple`` node.

        If *node_id* is ``None``, the first matching node is used.
        """
        node = self._resolve_node("CheckpointLoaderSimple", node_id)
        node.set_input("ckpt_name", ckpt_name)
        return node

    def set_vae(self, vae_name: str, *, node_id: str | None = None) -> ComfyNode:
        """Set the VAE on a ``VAELoader`` node."""
        node = self._resolve_node("VAELoader", node_id)
        node.set_input("vae_name", vae_name)
        return node

    def set_positive_prompt(self, text: str, *, node_id: str | None = None) -> ComfyNode:
        """Set the positive prompt text on a ``CLIPTextEncode`` node.

        If multiple ``CLIPTextEncode`` nodes exist and *node_id* is ``None``,
        the first one found is used.  For precise control, pass *node_id*.
        """
        return self._set_prompt(text, node_id, index=0)

    def set_negative_prompt(self, text: str, *, node_id: str | None = None) -> ComfyNode:
        """Set the negative prompt text on a ``CLIPTextEncode`` node.

        With multiple prompt nodes, the second one is targeted by default.
        """
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
    ) -> ComfyNode:
        """Update sampler parameters on a ``KSampler`` or ``KSamplerAdvanced`` node.

        Only the provided parameters are updated; others are left unchanged.
        """
        # Try KSamplerAdvanced first, then KSampler
        node = self._find_sampler_node(node_id)
        if seed is not None:
            # KSampler uses "seed", KSamplerAdvanced uses "noise_seed"
            if "noise_seed" in node.inputs:
                node.set_input("noise_seed", seed)
            elif "seed" in node.inputs:
                node.set_input("seed", seed)
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
    ) -> ComfyNode:
        """Set width/height on an ``EmptyLatentImage`` node."""
        node = self._resolve_node("EmptyLatentImage", node_id)
        if width is not None:
            node.set_input("width", width)
        if height is not None:
            node.set_input("height", height)
        return node

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_node(self, class_type: str, node_id: str | None) -> ComfyNode:
        """Find a node by *class_type* (or *node_id* if given).  Raises on miss."""
        if node_id is not None:
            node = self._nodes.get(node_id)
            if node is None:
                raise KeyError(f"Node {node_id!r} not found")
            return node
        matches = self.nodes_by_type(class_type)
        if not matches:
            raise KeyError(f"No node with class_type={class_type!r} found in workflow")
        return matches[0]

    def _set_prompt(self, text: str, node_id: str | None, *, index: int) -> ComfyNode:
        """Set prompt text, targeting the *index*-th CLIPTextEncode node if no *node_id*."""
        if node_id is not None:
            node = self._nodes.get(node_id)
            if node is None:
                raise KeyError(f"Node {node_id!r} not found")
        else:
            matches = self.nodes_by_type("CLIPTextEncode")
            if len(matches) <= index:
                raise KeyError(
                    f"Need at least {index + 1} CLIPTextEncode node(s), found {len(matches)}"
                )
            node = matches[index]
        node.set_input("text", text)
        return node

    def _find_sampler_node(self, node_id: str | None) -> ComfyNode:
        """Find a KSampler or KSamplerAdvanced node."""
        if node_id is not None:
            node = self._nodes.get(node_id)
            if node is None:
                raise KeyError(f"Node {node_id!r} not found")
            return node
        for cls in ("KSamplerAdvanced", "KSampler"):
            matches = self.nodes_by_type(cls)
            if matches:
                return matches[0]
        raise KeyError("No KSampler or KSamplerAdvanced node found in workflow")

    def __repr__(self) -> str:
        """Return a developer-friendly string representation."""
        return f"WorkflowBuilder({len(self._nodes)} nodes)"

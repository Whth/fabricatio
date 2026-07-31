"""Domain-specific workflow setter ABCs.

Each ``*Ops`` ABC captures one family of ComfyUI node-type conveniences
(``CheckpointLoaderSimple`` / ``VAELoader`` / ``CLIPTextEncode`` /
``KSampler`` / ``EmptyLatentImage`` / ``ResolutionSelector``) and is
composed into the concrete :class:`fabricatio_comfyui.models.workflow.Workflow`
via nominal multiple inheritance::

    class Workflow(WorkflowCore, LoaderOps, PromptOps, SamplerOps, ResolutionOps): ...

Splitting the setters out of the graph container keeps each concern in a
small, auditable unit and stops the graph class from baking in knowledge of
every ComfyUI node type.  Adding a new node family is a new ``*Ops`` ABC
plus one more base in ``Workflow``'s bases — no plugin dict, no ``hasattr``,
no runtime dispatch.

Every ``*Ops`` mixin inherits :class:`WorkflowAccess`, which declares the
core helpers (``_resolve`` / ``_require_node`` / ``by_type``) it depends on
as abstract methods.  :class:`WorkflowCore` provides the concrete
implementations, so the composed ``Workflow`` satisfies the contract through
nominal inheritance — no duck typing, no attribute sniffing.
"""

from abc import ABC, abstractmethod

from fabricatio_comfyui.models.workflow_core import (
    RESOLUTION_SELECTOR_ASPECT_RATIOS,
    Node,
)

__all__ = [
    "LoaderOps",
    "PromptOps",
    "ResolutionOps",
    "SamplerOps",
    "WorkflowAccess",
]

# Well-known ComfyUI node class names — declared once, reused by every mixin.
_CHECKPOINT_LOADER = "CheckpointLoaderSimple"
_VAE_LOADER = "VAELoader"
_CLIP_TEXT_ENCODE = "CLIPTextEncode"
_KSAMPLER_ADVANCED = "KSamplerAdvanced"
_KSAMPLER = "KSampler"
_EMPTY_LATENT_IMAGE = "EmptyLatentImage"
_RESOLUTION_SELECTOR = "ResolutionSelector"


# ------------------------------------------------------------------
# WorkflowAccess — the core-helper contract every *Ops mixin requires
# ------------------------------------------------------------------


class WorkflowAccess(ABC):
    """Abstract contract for the core graph helpers the ``*Ops`` mixins call.

    Declared separately from :class:`WorkflowCore` so that each ``*Ops`` ABC
    can name its dependencies through *nominal* inheritance rather than
    reaching for ``hasattr`` / ``getattr``.  ``WorkflowCore`` provides the
    concrete implementations; the composed ``Workflow`` satisfies this
    contract through its MRO.
    """

    @abstractmethod
    def _resolve(self, type: str, node_id: str | None) -> Node:
        """Return the node for *type* (first match) or the explicit *node_id*."""

    @abstractmethod
    def _require_node(self, node_id: str) -> Node:
        """Return the node for *node_id* or raise ``KeyError``."""

    @abstractmethod
    def by_type(self, type: str) -> list[Node]:
        """Find all nodes with the given *type*."""


# ------------------------------------------------------------------
# LoaderOps — checkpoint + VAE loaders
# ------------------------------------------------------------------


class LoaderOps(WorkflowAccess, ABC):
    """Typed setters for ``CheckpointLoaderSimple`` and ``VAELoader`` nodes."""

    def set_checkpoint(self, ckpt_name: str, *, node_id: str | None = None) -> Node:
        """Set the checkpoint on a ``CheckpointLoaderSimple`` node."""
        node = self._resolve(_CHECKPOINT_LOADER, node_id)
        node.set_input("ckpt_name", ckpt_name)
        return node

    def set_vae(self, vae_name: str, *, node_id: str | None = None) -> Node:
        """Set the VAE on a ``VAELoader`` node."""
        node = self._resolve(_VAE_LOADER, node_id)
        node.set_input("vae_name", vae_name)
        return node


# ------------------------------------------------------------------
# PromptOps — positive / negative CLIPTextEncode
# ------------------------------------------------------------------


class PromptOps(WorkflowAccess, ABC):
    """Typed setters for positive / negative ``CLIPTextEncode`` nodes."""

    def set_positive_prompt(self, text: str, *, node_id: str | None = None) -> Node:
        """Set the positive prompt text on a ``CLIPTextEncode`` node."""
        return self._set_prompt(text, node_id, index=0)

    def set_negative_prompt(self, text: str, *, node_id: str | None = None) -> Node:
        """Set the negative prompt text on a ``CLIPTextEncode`` node (second one)."""
        return self._set_prompt(text, node_id, index=1)

    def _set_prompt(self, text: str, node_id: str | None, *, index: int) -> Node:
        if node_id is not None:
            node = self._require_node(node_id)
        else:
            matches = self.by_type(_CLIP_TEXT_ENCODE)
            if len(matches) <= index:
                raise KeyError(f"Need at least {index + 1} CLIPTextEncode node(s), found {len(matches)}")
            node = matches[index]
        node.set_input("text", text)
        return node


# ------------------------------------------------------------------
# SamplerOps — KSampler / KSamplerAdvanced
# ------------------------------------------------------------------


class SamplerOps(WorkflowAccess, ABC):
    """Typed setter for ``KSampler`` / ``KSamplerAdvanced`` parameters."""

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

    def _find_sampler(self, node_id: str | None) -> Node:
        if node_id is not None:
            return self._require_node(node_id)
        for sampler_type in (_KSAMPLER_ADVANCED, _KSAMPLER):
            matches = self.by_type(sampler_type)
            if matches:
                return matches[0]
        raise KeyError("No KSampler or KSamplerAdvanced node found in workflow")


# ------------------------------------------------------------------
# ResolutionOps — EmptyLatentImage + ResolutionSelector
# ------------------------------------------------------------------


class ResolutionOps(WorkflowAccess, ABC):
    """Typed setters for ``EmptyLatentImage`` and ``ResolutionSelector`` nodes."""

    def set_resolution(
        self,
        *,
        width: int | None = None,
        height: int | None = None,
        node_id: str | None = None,
    ) -> Node:
        """Set width/height on an ``EmptyLatentImage`` node."""
        node = self._resolve(_EMPTY_LATENT_IMAGE, node_id)
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
            node = self._require_node(node_id)
            if node.type != _RESOLUTION_SELECTOR:
                raise KeyError(f"Node {node_id!r} is {node.type!r}, not ResolutionSelector")
        else:
            matches = self.by_type(_RESOLUTION_SELECTOR)
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

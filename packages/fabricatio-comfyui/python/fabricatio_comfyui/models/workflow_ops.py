"""Domain-specific workflow builder ABCs.

Each ``*Ops`` ABC captures one family of ComfyUI node-type conveniences
(``CheckpointLoaderSimple`` / ``VAELoader`` / ``CLIPTextEncode`` /
``KSampler`` / ``EmptyLatentImage`` / ``ResolutionSelector``) and is
composed into the concrete :class:`fabricatio_comfyui.models.workflow.Workflow`
via nominal multiple inheritance::

    class Workflow(WorkflowCore, LoaderOps, PromptOps, SamplerOps, ResolutionOps): ...

Splitting the builders out of the graph container keeps each concern in a
small, auditable unit and stops the graph class from baking in knowledge of
every ComfyUI node type.  Adding a new node family is a new ``*Ops`` ABC
plus one more base in ``Workflow``'s bases — no plugin dict, no ``hasattr``,
no runtime dispatch.

Every ``with_*`` builder mutates the workflow in place and returns *self*
(Rust consuming-builder style), so configuration reads as a chain::

    wf.with_positive_prompt("a mountain").with_sampler(seed=42).with_resolution(width=1024)

Every ``*Ops`` mixin inherits :class:`WorkflowAccess`, which declares the
core helpers (``_resolve`` / ``_require_node`` / ``by_type``) it depends on
as abstract methods.  :class:`WorkflowCore` provides the concrete
implementations, so the composed ``Workflow`` satisfies the contract through
nominal inheritance — no duck typing, no attribute sniffing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Self

from fabricatio_comfyui.models.workflow_core import (
    RESOLUTION_SELECTOR_ASPECT_RATIOS,
    Node,
)

__all__ = [
    "AspectRatioSpec",
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
    def _resolve(self, node_type: str, node_id: str | None) -> Node:
        """Return the node for *node_type* (first match) or the explicit *node_id*."""

    @abstractmethod
    def _require_node(self, node_id: str) -> Node:
        """Return the node for *node_id* or raise ``KeyError``."""

    @abstractmethod
    def by_type(self, node_type: str) -> list[Node]:
        """Find all nodes with the given *type*."""


# ------------------------------------------------------------------
# LoaderOps — checkpoint + VAE loaders
# ------------------------------------------------------------------


class LoaderOps(WorkflowAccess, ABC):
    """Chainable builders for ``CheckpointLoaderSimple`` and ``VAELoader`` nodes."""

    def with_checkpoint(self, ckpt_name: str, *, node_id: str | None = None) -> Self:
        """Set the checkpoint on a ``CheckpointLoaderSimple`` node; return *self* for chaining."""
        node = self._resolve(_CHECKPOINT_LOADER, node_id)
        node.set_input("ckpt_name", ckpt_name)
        return self

    def with_vae(self, vae_name: str, *, node_id: str | None = None) -> Self:
        """Set the VAE on a ``VAELoader`` node; return *self* for chaining."""
        node = self._resolve(_VAE_LOADER, node_id)
        node.set_input("vae_name", vae_name)
        return self


class PromptOps(WorkflowAccess, ABC):
    """Chainable builders for positive / negative ``CLIPTextEncode`` nodes."""

    def with_positive_prompt(self, text: str, *, node_id: str | None = None) -> Self:
        """Set the positive prompt text on a ``CLIPTextEncode`` node; return *self* for chaining."""
        self._set_prompt(text, node_id, index=0)
        return self

    def with_negative_prompt(self, text: str, *, node_id: str | None = None) -> Self:
        """Set the negative prompt text on the second ``CLIPTextEncode`` node; return *self*."""
        self._set_prompt(text, node_id, index=1)
        return self

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


class SamplerOps(WorkflowAccess, ABC):
    """Chainable builder for ``KSampler`` / ``KSamplerAdvanced`` parameters."""

    def with_sampler(
        self,
        *,
        seed: int | None = None,
        steps: int | None = None,
        cfg: float | None = None,
        sampler_name: str | None = None,
        scheduler: str | None = None,
        denoise: float | None = None,
        node_id: str | None = None,
    ) -> Self:
        """Update sampler parameters on a ``KSampler`` or ``KSamplerAdvanced`` node; return *self*."""
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
        return self

    def _find_sampler(self, node_id: str | None) -> Node:
        if node_id is not None:
            return self._require_node(node_id)
        for sampler_type in (_KSAMPLER_ADVANCED, _KSAMPLER):
            matches = self.by_type(sampler_type)
            if matches:
                return matches[0]
        raise KeyError("No KSampler or KSamplerAdvanced node found in workflow")


# ------------------------------------------------------------------
# AspectRatioSpec — validated knob bundle for a ResolutionSelector node
# ------------------------------------------------------------------


@dataclass(frozen=True)
class AspectRatioSpec:
    """Validated knob bundle for a ComfyUI ``ResolutionSelector`` node.

    Parse-don't-validate: build the spec from raw knobs, call :meth:`validated`
    to reject bad aspect tokens up front, then :meth:`apply_to` writes only the
    provided (non-``None``) values onto the node.
    """

    aspect_ratio: str | None = None
    """ComfyUI aspect token, e.g. ``"16:9 (Widescreen)"``; ``None`` leaves it unchanged."""

    megapixels: float | None = None
    """Target megapixels e.g. ``1.7``; ``None`` leaves it unchanged."""

    multiple: int | None = None
    """Pixel-alignment multiple e.g. ``12``; ``None`` leaves it unchanged."""

    @classmethod
    def from_knobs(
        cls, aspect_ratio: str | None = None, megapixels: float | None = None, multiple: int | None = None
    ) -> Self:
        """Build a spec from raw caller knobs."""
        return cls(aspect_ratio=aspect_ratio, megapixels=megapixels, multiple=multiple)

    def validated(self) -> Self:
        """Return *self* unless *aspect_ratio* is outside :data:`RESOLUTION_SELECTOR_ASPECT_RATIOS`."""
        if self.aspect_ratio is not None and self.aspect_ratio not in RESOLUTION_SELECTOR_ASPECT_RATIOS:
            valid = ", ".join(sorted(RESOLUTION_SELECTOR_ASPECT_RATIOS, key=lambda s: float(s.split(":")[0])))
            raise ValueError(
                f"Invalid aspect_ratio {self.aspect_ratio!r}. Valid values for the current ResolutionSelector: {valid}.",
            )
        return self

    def apply_to(self, node: Node) -> None:
        """Write the provided (non-``None``) knobs onto *node*."""
        for name, value in (
            ("aspect_ratio", self.aspect_ratio),
            ("megapixels", self.megapixels),
            ("multiple", self.multiple),
        ):
            if value is not None:
                node.set_input(name, value)


# ------------------------------------------------------------------
# ResolutionOps — EmptyLatentImage + ResolutionSelector
# ------------------------------------------------------------------


class ResolutionOps(WorkflowAccess, ABC):
    """Chainable builders for ``EmptyLatentImage`` and ``ResolutionSelector`` nodes."""

    def with_resolution(
        self,
        *,
        width: int | None = None,
        height: int | None = None,
        node_id: str | None = None,
    ) -> Self:
        """Set width/height on an ``EmptyLatentImage`` node; return *self* for chaining."""
        node = self._resolve(_EMPTY_LATENT_IMAGE, node_id)
        if width is not None:
            node.set_input("width", width)
        if height is not None:
            node.set_input("height", height)
        return self

    def with_aspect_ratio(
        self,
        *,
        aspect_ratio: str | None = None,
        megapixels: float | None = None,
        multiple: int | None = None,
        node_id: str | None = None,
    ) -> Self:
        """Set the aspect ratio on a ``ResolutionSelector`` node; return *self* for chaining.

        Only the parameters that are provided (not ``None``) get written — pass
        ``None`` to leave the current value unchanged.  Validation and writing are
        delegated to :class:`AspectRatioSpec`.

        Args:
            aspect_ratio: ComfyUI aspect ratio string, e.g. ``"16:9 (Widescreen)"``.
                Must be one of :data:`RESOLUTION_SELECTOR_ASPECT_RATIOS`.
            megapixels: Target megapixels e.g. ``1.7`` (float).
            multiple: Multiple constraint e.g. ``12`` (pixel alignment).
            node_id: Explicit node ID.  If omitted, uses the first ``ResolutionSelector``.

        Returns:
            *self*, for chaining.

        Raises:
            KeyError: If no ``ResolutionSelector`` node exists and no *node_id* is given,
                or *node_id* does not exist.
            ValueError: If *aspect_ratio* is not in :data:`RESOLUTION_SELECTOR_ASPECT_RATIOS`.
        """
        node = self._resolve_selector(node_id)
        AspectRatioSpec.from_knobs(aspect_ratio, megapixels, multiple).validated().apply_to(node)
        return self

    def _resolve_selector(self, node_id: str | None) -> Node:
        """Locate the target ``ResolutionSelector`` — by explicit ID or first match."""
        if node_id is not None:
            node = self._require_node(node_id)
            if node.type != _RESOLUTION_SELECTOR:
                raise KeyError(f"Node {node_id!r} is {node.type!r}, not ResolutionSelector")
            return node
        matches = self.by_type(_RESOLUTION_SELECTOR)
        if not matches:
            raise KeyError(
                "No ResolutionSelector node found in workflow. "
                "Use with_resolution() for literal dimensions, or add a ResolutionSelector node.",
            )
        return matches[0]

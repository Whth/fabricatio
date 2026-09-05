"""Propose-able image-generation specifications.

``SketchSpec`` bundles everything a text-to-image generation needs — the
positive prompt, the negative prompt, and the canvas size (aspect-ratio
preset + megapixel budget) — so one :meth:`propose` call yields a
complete generation instruction that the LLM itself sizes per subject.
"""

from fabricatio_core.models.generic import SketchedAble
from pydantic import Field, field_validator

from fabricatio_comfyui.models.resolution import Prop

__all__ = ["SketchSpec"]


class SketchSpec(SketchedAble):
    """A complete image-generation instruction, fillable in one proposal.

    Use it as the target of
    :meth:`fabricatio_core.capabilities.propose.Propose.propose`: the LLM
    reads the caller's scene text and returns the positive prompt, the
    negative prompt, and the canvas it wants — no manual per-knob
    prompting.  ``None`` size fields fall back at generation time to the
    config/template chain (``[ext.comfyui] mp/prop``, then the active
    workflow template's canvas).
    """

    prompt: str
    """The image-generation prompt (positive prompt), in English."""

    negative_prompt: str = ""
    """What the image must avoid; empty when nothing is excluded."""

    mp: float | None = Field(default=None, gt=0)
    """Megapixel budget of the latent canvas (``1.0`` = 1,000,000 pixels).

    Pick a budget that fits the subject's detail; ``None`` falls back to
    :data:`fabricatio_comfyui.config.comfyui_config.mp`, then the active
    template's canvas area.
    """

    prop: Prop | None = None
    """Aspect-ratio preset of the canvas; ``None`` keeps the fallback ratio.

    Accepts ``"16:9"`` style values or ``prop_16_9``-style names (e.g.
    ``prop_2_3`` for a portrait scene).  Choose the preset that fits the
    composition; ``None`` falls back to the config/template canvas ratio.
    """

    @field_validator("prop", mode="before")
    @classmethod
    def _coerce_prop(cls, value: object) -> object:
        """Map ``"16:9"`` / ``"prop_16_9"`` spellings onto the enum member."""
        return Prop.of(value) if isinstance(value, str) else value

"""Models for the illustration pipeline.

Provides :class:`IllustrationConstrain` (the typed result of
stage 2 of the illustration pipeline, holding both frame proportion and the
image-generation prompt).
"""

from fabricatio_comfyui.models.workflow import FrameAspect
from fabricatio_core.models.generic import ProposedAble
from pydantic import Field


class IllustrationConstrain(ProposedAble):
    """Typed result of stage 2 of the illustration pipeline.

    Replaces the previous plain-string image prompt. Carries both the frame
    proportion (forwarded to a ComfyUI ``ResolutionSelector`` node via
    :meth:`fabricatio_comfyui.models.workflow.Workflow.set_chart_proportion`)
    and the actual generation prompt (forwarded via
    :meth:`fabricatio_comfyui.models.workflow.Workflow.set_positive_prompt`).
    """

    aspect_ratio: FrameAspect
    """ComfyUI ``ResolutionSelector`` aspect-ratio token for this image."""

    megapixels: float = Field(ge=0.0, default=1.0)
    """Target megapixel count for this image. Forwarded to the
    ``ResolutionSelector`` ``megapixels`` input."""

    prompt: str
    """The image-generation prompt, written in ComfyUI tag format."""

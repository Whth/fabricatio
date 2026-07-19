"""Models for the illustration pipeline.

Provides :class:`FrameAspect` (the verbatim ComfyUI ``ResolutionSelector``
aspect-ratio tokens) and :class:`IllustrationConstrain` (the typed result of
stage 2 of the illustration pipeline, holding both frame proportion and the
image-generation prompt).
"""

from enum import StrEnum
from typing import Tuple

from pydantic import Field

from fabricatio_core.models.generic import ProposedAble


class FrameAspect(StrEnum):
    """Verbatim ComfyUI ``ResolutionSelector`` aspect-ratio tokens.

    Each member's value is the exact string ComfyUI expects on the
    ``aspect_ratio`` input of a ``ResolutionSelector`` node. Each member also
    exposes its numeric (width, height) ratio via :attr:`ratio`, used by the
    literal-dimension fallback path (workflows without a
    ``ResolutionSelector`` node).
    """

    SQUARE = "square"
    PHOTO = "photo"
    PORTRAIT_PHOTO = "portrait photo"
    PORTRAIT_STANDARD = "portrait standard"
    STANDARD = "standard"
    WIDESCREEN_PORTRAIT = "widescreen portrait"
    WIDESCREEN = "widescreen"
    ULTRAWIDE = "ultrawide"

    @property
    def ratio(self) -> Tuple[int, int]:
        """Numeric (width, height) ratio for this aspect token.

        Used to derive literal pixel dimensions from a target megapixel count
        for workflows that drive ``EmptyLatentImage.width/height`` directly
        rather than through a ``ResolutionSelector`` node.
        """
        match self:
            case FrameAspect.SQUARE:
                return 1, 1
            case FrameAspect.PHOTO:
                return 3, 2
            case FrameAspect.PORTRAIT_PHOTO:
                return 2, 3
            case FrameAspect.PORTRAIT_STANDARD:
                return 3, 4
            case FrameAspect.STANDARD:
                return 5, 4
            case FrameAspect.WIDESCREEN_PORTRAIT:
                return 9, 16
            case FrameAspect.WIDESCREEN:
                return 16, 9
            case FrameAspect.ULTRAWIDE:
                return 21, 9


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

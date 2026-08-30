"""Illustration models: the LLM proposal target and the illustrated scene output."""

from typing import Self

from fabricatio_core.models.generic import SketchedAble

from fabricatio_novel.models.context.illustration import IllustratedSceneContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.scene import Scene

__all__ = ["IllustratedScene", "SceneIllustration"]


class SceneIllustration(SketchedAble):
    """A scene's illustration specification: the image prompt plus its negative prompt."""

    prompt: str
    """The image-generation prompt describing the scene's key visual, in English."""

    negative_prompt: str = ""
    """Text describing what the image must avoid; empty when nothing is excluded."""


class IllustratedScene(Scene):
    """A composed scene carrying its illustration, materialized from an illustrated context."""

    illustration_prompt: str = ""
    """The image-generation prompt proposed for this scene; empty until illustrated."""

    illustration_image: str = ""
    """Absolute path of the rendered illustration PNG; empty until illustrated."""

    @classmethod
    def from_context(cls, ctx: SceneContext) -> Self:
        """Materialize an illustrated scene; the illustration channel copies when the context carries it."""
        scene = super().from_context(ctx)
        if isinstance(ctx, IllustratedSceneContext):
            scene.illustration_prompt = ctx.illustration_prompt
            scene.illustration_image = ctx.illustration_image
        return scene

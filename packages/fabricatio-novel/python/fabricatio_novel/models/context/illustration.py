"""Illustration channel context: a scene context subclass carrying per-scene illustration state."""

from typing import Self

from fabricatio_novel.models.context.scene import SceneContext

__all__ = ["IllustratedSceneContext"]


class IllustratedSceneContext(SceneContext):
    """A scene context extended with the illustration channel.

    Runs that compose novels without illustrations keep plain
    :class:`~fabricatio_novel.models.context.scene.SceneContext` trees and never see this
    subclass; the illustration capability isinstance-gates on it, so the choice between
    illustrated and plain generation is made by the workflow's stages alone.
    """

    illustration_prompt: str = ""
    """The image-generation prompt proposed for this scene; empty until illustrated."""

    illustration_image: str = ""
    """Absolute path of the rendered illustration PNG; empty until illustrated."""

    def set_illustration(self, prompt: str, image: str) -> Self:
        """Record the scene's illustration prompt and rendered image path, and return self."""
        self.illustration_prompt = prompt
        self.illustration_image = image
        return self

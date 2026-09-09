"""Illustration models: the illustrated scene output and per-role settings.

The propose-able generation instruction for scene illustrations is the
ComfyUI :class:`~fabricatio_comfyui.models.specs.SketchSpec` (positive
prompt, negative prompt, and canvas); the models below carry the rendered
result and the scoped settings.
"""

import html
from pathlib import Path
from typing import Self

from fabricatio_core.models.generic import ScopedConfig

from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.scene import Scene
from fabricatio_novel.utils import scene_image_name

__all__ = ["IllustratedScene", "IllustrationScopedConfig"]


class IllustrationScopedConfig(ScopedConfig):
    """Per-instance illustration settings with hierarchical fallback.

    Fields default to ``None`` (unset at this scope) and resolve through
    the framework's scoped-config chain: a per-call argument wins, then
    this instance's field, then the global
    :data:`fabricatio_novel.config.novel_config`.  Roles compose this
    class through :class:`~fabricatio_novel.capabilities.illustration.IllustrateScenes`
    and propagate their values to workflows and steps via
    :meth:`hold_to` / :meth:`fallback_to`.
    """

    illustration_constraint: str | None = None
    """Global style/content constraint merged into every illustration prompt proposal.

    Used by :meth:`IllustrateScenes.illustrate_novel_phase` when no per-call
    ``illustration_constraint`` is given; falls back to the global
    ``[ext.novel] illustration_constraint``.
    """

    illustration_choose_loras: bool | None = None
    """Per-instance opt-in for catalog LoRA selection; ``None`` falls back to the global
    ``[ext.novel] illustration_choose_loras``."""


class IllustratedScene(Scene):
    """A composed scene carrying its rendered illustration."""

    illustration_prompt: str = ""
    """The image-generation prompt proposed for this scene; empty until illustrated."""

    illustration_image: str = ""
    """Absolute path of the rendered illustration PNG; empty until illustrated."""

    @classmethod
    def from_context(
        cls,
        ctx: SceneContext,
        *,
        illustration_prompt: str = "",
        illustration_image: str = "",
    ) -> Self:
        """Materialize an illustrated scene from its context, recording the rendered illustration."""
        return cls(
            title=ctx.title,
            description=ctx.description,
            expected_word_count=ctx.expected_word_count,
            writing_styles=list(ctx.plan.writing_styles) if ctx.plan is not None else [],
            writing_constraints=list(ctx.writing_constraints),
            content=ctx.content,
            illustration_prompt=illustration_prompt,
            illustration_image=illustration_image,
        )

    def to_xhtml(self, chapter_index: int, scene_index: int) -> str:
        """Render the scene's paragraphs followed by its illustration figure."""
        sections = [super().to_xhtml(chapter_index, scene_index)]
        if self.illustration_image:
            sections.append(
                f'<figure class="illustration"><img src="images/{scene_image_name(chapter_index, scene_index)}" '
                f'alt="{html.escape(self.title)}"/></figure>'
            )
        return "\n".join(sections)

    def epub_resources(self, chapter_index: int, scene_index: int) -> list[tuple[str, Path]]:
        """Return this scene's illustration as an EPUB image resource, or nothing before one exists."""
        if not self.illustration_image:
            return []
        return [(f"images/{scene_image_name(chapter_index, scene_index)}", Path(self.illustration_image))]

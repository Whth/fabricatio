"""Output model for a composed scene: the scene plan plus its composed prose."""

from typing import Self

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core.rust import word_count

from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.plan import ScenePlan


class Scene(ScenePlan, WordCount):
    """A composed scene: its plan fields and the written content."""

    content: str

    @property
    def exact_word_count(self) -> int:
        return word_count(self.content)

    @classmethod
    def from_context(cls, ctx: SceneContext) -> Self:
        """Materialize a scene from its scene context."""
        return cls(
            title=ctx.title,
            description=ctx.description,
            expected_word_count=ctx.expected_word_count,
            content=ctx.content,
        )

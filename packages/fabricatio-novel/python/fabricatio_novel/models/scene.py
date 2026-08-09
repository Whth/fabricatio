from typing import Self

from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.plan import ScenePlan


class Scene(ScenePlan):
    content: str

    @classmethod
    def from_context(cls, ctx: SceneContext) -> Self:
        return cls(
            title=ctx.title,
            description=ctx.description,
            expected_word_count=ctx.expected_word_count,
            content=ctx.content,
        )

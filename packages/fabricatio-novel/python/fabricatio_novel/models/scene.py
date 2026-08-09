from typing import Self

from fabricatio_capabilities.models.generic import WordCount

from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.plan import ScenePlan


class Scene(ScenePlan, WordCount):
    content: str

    @classmethod
    def from_context(cls, ctx: SceneContext) -> Self:
        return cls(
            title=ctx.title,
            description=ctx.description,
            expected_word_count=ctx.expected_word_count,
            content=ctx.content,
        )

from typing import List, Self

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import StoryPlan
from fabricatio_novel.models.scene import Scene


class Story(StoryPlan, WordCount):
    scenes: List[Scene]

    @classmethod
    def from_context(cls, ctx: StoryContext) -> Self:
        return cls(
            title=ctx.title,
            description=ctx.description,
            expected_word_count=ctx.expected_word_count,
            scenes=[Scene.from_context(sc) for sc in ctx.scene_context],
        )

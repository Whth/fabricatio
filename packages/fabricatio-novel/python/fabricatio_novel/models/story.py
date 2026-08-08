from typing import List, Self

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core.models.generic import Described
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.scene import Scene


class Story(Described, WordCount):
    scenes: List[Scene]

    @classmethod
    def from_context(cls, ctx: StoryContext) -> Self: ...

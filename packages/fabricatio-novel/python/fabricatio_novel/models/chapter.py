from typing import List, Self

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core.models.generic import Titled, Described
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.story import Story


class Chapter(Titled, Described, WordCount):
    story: List[Story]

    @classmethod
    def from_context(cls, ctx: ChapterContext) -> Self: ...

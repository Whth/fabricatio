from typing import List, Self

from fabricatio_capabilities.models.generic import PersistentAble, WordCount
from fabricatio_core.models.generic import Titled, Described
from fabricatio_novel.models.chapter import Chapter
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.series_book import SeriesBible


class NovelMetadata(Titled, Described, WordCount):
    series_bible: SeriesBible


class Novel(PersistentAble, NovelMetadata):
    chapter: List[Chapter]

    @classmethod
    def from_context(cls, ctx: NovelContext) -> Self: ...

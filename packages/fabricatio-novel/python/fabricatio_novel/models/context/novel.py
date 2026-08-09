from typing import Self

from pydantic import Field

from fabricatio_core.rust import detect_language
from fabricatio_novel.models.context.base import ChainableContext, ContextBase
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.series_book import SeriesBible


class NovelContext(ChainableContext, ContextBase):
    outline: str
    language: str

    series_bible: SeriesBible = Field(default_factory=SeriesBible)

    chapter_plan: list[ChapterPlan] = Field(default_factory=list)
    """Planned chapters; proposed before the chapter contexts are created."""

    chapter_context: list[ChapterContext] = Field(default_factory=list)

    def set_series_bible(self, series_bible: SeriesBible) -> Self:
        self.series_bible = series_bible
        return self

    def set_chapter_plan(self, plans: list[ChapterPlan]) -> Self:
        self.chapter_plan = plans
        return self

    def set_chapter_contexts(self, chapters: list[ChapterContext]) -> Self:
        self.chapter_context = chapters
        return self

    def add_chapter_context(self, chapter: ChapterContext) -> Self:
        self.chapter_context.append(chapter)
        return self

    @classmethod
    def create(cls, outline: str, language: str | None = None) -> Self:
        return cls(outline=outline, language=language or detect_language(outline))

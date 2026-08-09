from typing import Self

from pydantic import Field

from fabricatio_core.rust import detect_language
from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.series_book import SeriesBible


class NovelContext(ContextBase):
    outline: str
    language: str

    title: str = ""
    description: str = ""

    series_bible: SeriesBible = Field(default_factory=SeriesBible)

    chapter_context: list[ChapterContext] = Field(default_factory=list)

    @classmethod
    def create(cls, outline: str, language: str | None = None) -> Self:
        return cls(outline=outline, language=language or detect_language(outline))

from typing import Generator, Self, final

from fabricatio_core.rust import detect_language
from pydantic import Field

from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.plan import NovelPlan


class NovelContext(ContextBase):
    outline: str
    language: str

    title: str = ""
    description: str = ""

    novel_plan: NovelPlan | None = None
    """The novel's own plan; proposed before the chapter contexts are created."""

    chapter_context: list[ChapterContext] = Field(default_factory=list)

    @final
    def iter_chapter_content(self) -> Generator[str, None, None]:
        """Yield each chapter's composed content, in novel order."""
        for chapter_ctx in self.chapter_context:
            yield from chapter_ctx.iter_story_content()

    @final
    def iter_child_contexts(self) -> Generator[ChapterContext, None, None]:
        """Yield this novel's chapter contexts, in composition order."""
        yield from self.chapter_context

    def set_novel_plan(self, plan: NovelPlan) -> Self:
        self.novel_plan = plan
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

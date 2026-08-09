from typing import Generator, Self, final

from fabricatio_capabilities.models.generic import UpdateFrom
from fabricatio_core.rust import detect_language
from pydantic import Field

from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.plan import NovelPlan


class NovelContext(UpdateFrom, ContextBase):
    outline: str
    language: str

    title: str = ""
    description: str = ""

    novel_plan: NovelPlan | None = None
    """The novel's own plan; proposed before the chapter contexts are created."""

    chapter_context: list[ChapterContext] = Field(default_factory=list)

    def update_pre_check(self, other: NovelPlan | Self) -> Self:
        """Accept a novel plan (or another novel context) as the update source."""
        if not isinstance(other, (NovelPlan, NovelContext)):
            raise TypeError(f"Cannot update {self.__class__.__name__} from a {other.__class__.__name__} instance.")
        return self

    def update_from_inner(self, other: NovelPlan | Self) -> Self:
        """Adopt the plan's fields; the settings bible is adopted only when it carries content."""
        self.title = other.title
        self.description = other.description
        self.expected_word_count = other.expected_word_count
        if other.series_bible is not None and not other.series_bible.is_empty():
            self.series_bible = other.series_bible
        return self

    @final
    def iter_chapter_content(self) -> Generator[str, None, None]:
        """Yield each chapter's composed content, in novel order."""
        for chapter_ctx in self.chapter_context:
            yield from chapter_ctx.iter_story_content()

    @final
    def iter_child_contexts(self) -> Generator[ChapterContext, None, None]:
        """Yield this novel's chapter contexts, in composition order."""
        yield from self.chapter_context

    @final
    def iter_prefixed_contexts(self) -> Generator[ChapterContext, None, None]:
        """Set each chapter's running prefixed content in place and yield it.

        Composed content is read live at each step, so in-place updates made
        while iterating are reflected in the following chapters' prefixes.
        """
        prefix = self.prefixed_content
        for chapter_ctx in self.chapter_context:
            chapter_ctx.set_prefixed_content(prefix)
            yield chapter_ctx
            prefix = "\n\n".join(p for p in (prefix, *chapter_ctx.iter_story_content()) if p)

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

"""Pipeline channel model for the novel root: outline, language and chapter contexts."""

from typing import Generator, Self, final

from fabricatio_capabilities.models.generic import UpdateFrom
from fabricatio_core.rust import detect_language
from pydantic import Field

from fabricatio_novel.models.context.base import CharacterSpan, ContextBase
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.log import ContextEntry
from fabricatio_novel.models.context.rag import RAGChannel
from fabricatio_novel.models.plan import NovelPlan


class NovelContext(UpdateFrom, RAGChannel, ContextBase[ChapterContext]):
    """The novel root channel: outline, language, plan and the chapter contexts it writes."""

    outline: str
    language: str

    title: str = ""
    description: str = ""

    novel_plan: NovelPlan | None = None
    """The novel's own plan; proposed before the chapter contexts are created."""

    chapter_context: list[ChapterContext] = Field(default_factory=list)

    charactor_span: list[CharacterSpan] = Field(default_factory=list)

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
        self.writing_style = other.writing_style
        self.writing_constraint = other.writing_constraint or self.writing_constraint
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
    def prefixed_entries(self) -> tuple[ContextEntry, ...]:
        """Forward the chapters' entries; the novel's own title is not injected."""
        entries: list[ContextEntry] = []
        for child in self.iter_child_contexts():
            entries.extend(child.prefixed_entries())
        return tuple(entries)

    def set_novel_plan(self, plan: NovelPlan) -> Self:
        """Set the novel's plan and return self."""
        self.novel_plan = plan
        return self

    def set_chapter_contexts(self, chapters: list[ChapterContext]) -> Self:
        """Replace the novel's chapter contexts and return self."""
        self.chapter_context = chapters
        return self

    def add_chapter_context(self, chapter: ChapterContext) -> Self:
        """Append a chapter context to the novel and return self."""
        self.chapter_context.append(chapter)
        return self

    def set_charactor_spans(self, spans: list[CharacterSpan]) -> Self:
        """Replace the novel's roster character spans and return self."""
        self.charactor_span = spans
        return self

    @classmethod
    def create(cls, outline: str, language: str | None = None) -> Self:
        """Build a novel context from an outline, detecting the language from the outline when none is given."""
        return cls(outline=outline, language=language or detect_language(outline))

    def dump_characters(self) -> str:
        """Render every character's start and end states for prompts, in span order."""
        return "\n".join(s.dump_to_prompt() for s in self.charactor_span)

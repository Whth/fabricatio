"""Pipeline channel model for a chapter: its plan and the story contexts it writes."""

from typing import ClassVar, Generator, Self, final

from fabricatio_core.models.generic import Described, Titled
from pydantic import Field

from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.rag import RAGChannel
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import ChapterPlan


class ChapterContext(RAGChannel, Titled, Described, ContextBase):
    """A chapter's composition channel: its plan, story contexts and heading block."""

    heading_level: ClassVar[str] = "#"

    chapter_plan: ChapterPlan | None = None
    """The chapter's own plan; proposed before the story contexts are created."""

    story_context: list[StoryContext] = Field(default_factory=list)

    @classmethod
    def from_plan(cls, plan: ChapterPlan, expected_word_count: int) -> Self:
        """Build the chapter context from its proposed plan."""
        return (
            cls(
                title=plan.title,
                description=plan.description,
                expected_word_count=expected_word_count,
            )
            .set_chapter_plan(plan)
            .set_writing_style(plan.writing_style)
        )

    @final
    def iter_story_content(self) -> Generator[str, None, None]:
        """Yield each story's composed content, in chapter order."""
        for story_ctx in self.story_context:
            yield from story_ctx.iter_scene_content()

    @final
    def iter_child_contexts(self) -> Generator[StoryContext, None, None]:
        """Yield this chapter's story contexts, in composition order."""
        yield from self.story_context

    @final
    def render_prefixed_header(self) -> str:
        """Render the chapter's heading block, seeded into each story's prefix."""
        return f"{self.heading_level} {self.title}\n\n> {self.description}"

    @final
    def render_prefixed_block(self) -> str:
        """Render the chapter's heading block followed by its story blocks."""
        parts: list[str] = [self.render_prefixed_header()]
        parts.extend(child.render_prefixed_block() for child in self.iter_child_contexts())
        return "\n\n".join(parts)

    def set_chapter_plan(self, plan: ChapterPlan) -> Self:
        """Set the chapter's plan and return self."""
        self.chapter_plan = plan
        return self

    def set_story_contexts(self, stories: list[StoryContext]) -> Self:
        """Replace the chapter's story contexts and return self."""
        self.story_context = stories
        return self

    def add_story_context(self, story: StoryContext) -> Self:
        """Append a story context to the chapter and return self."""
        self.story_context.append(story)
        return self

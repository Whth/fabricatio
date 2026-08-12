from typing import ClassVar, Generator, Self, final

from pydantic import Field

from fabricatio_core.models.generic import Described, Titled
from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.rag import RAGChannel
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import ChapterPlan


class ChapterContext(RAGChannel, Titled, Described, ContextBase):
    heading_level: ClassVar[str] = "#"

    chapter_plan: ChapterPlan | None = None
    """The chapter's own plan; proposed before the story contexts are created."""

    story_context: list[StoryContext] = Field(default_factory=list)

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
    def render_prefixed_block(self) -> str:
        """Render the chapter's title, description, and story blocks."""
        parts: list[str] = [f"{self.heading_level} {self.title}", f"> {self.description}"]
        parts.extend(child.render_prefixed_block() for child in self.iter_child_contexts())
        return "\n\n".join(parts)

    def set_chapter_plan(self, plan: ChapterPlan) -> Self:
        self.chapter_plan = plan
        return self

    def set_story_contexts(self, stories: list[StoryContext]) -> Self:
        self.story_context = stories
        return self

    def add_story_context(self, story: StoryContext) -> Self:
        self.story_context.append(story)
        return self

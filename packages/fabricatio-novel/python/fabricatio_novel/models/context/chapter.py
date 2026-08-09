from typing import Self

from pydantic import Field

from fabricatio_novel.models.context.base import ChainableContext, ContextBase
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import ChapterPlan


class ChapterContext(ChainableContext, ContextBase):
    chapter_plan: ChapterPlan | None = None
    """The chapter's own plan; proposed before the story contexts are created."""

    story_context: list[StoryContext] = Field(default_factory=list)

    def set_chapter_plan(self, plan: ChapterPlan) -> Self:
        self.chapter_plan = plan
        return self

    def set_story_contexts(self, stories: list[StoryContext]) -> Self:
        self.story_context = stories
        return self

    def add_story_context(self, story: StoryContext) -> Self:
        self.story_context.append(story)
        return self

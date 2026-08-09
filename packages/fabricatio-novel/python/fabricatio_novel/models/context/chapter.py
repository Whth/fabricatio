from typing import Self

from pydantic import Field

from fabricatio_novel.models.context.base import ChainableContext, ContextBase
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import StoryPlan


class ChapterContext(ChainableContext, ContextBase):
    story_plan: list[StoryPlan] = Field(default_factory=list)
    """Planned stories; proposed before the story contexts are created."""

    story_context: list[StoryContext] = Field(default_factory=list)

    def set_story_plan(self, plans: list[StoryPlan]) -> Self:
        self.story_plan = plans
        return self

    def set_story_contexts(self, stories: list[StoryContext]) -> Self:
        self.story_context = stories
        return self

    def add_story_context(self, story: StoryContext) -> Self:
        self.story_context.append(story)
        return self

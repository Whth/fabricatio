from fabricatio_core.models.generic import Described, Titled
from pydantic import Field
from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.story import StoryContext


class ChapterContext(Titled, Described, ContextBase):
    story_context: list[StoryContext] = Field(default_factory=list)

from typing import Self

from pydantic import Field

from fabricatio_novel.models.context.base import ChainableContext, ContextBase
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.plan import StoryPlan


class StoryContext(ChainableContext, ContextBase):
    story_plan: StoryPlan | None = None
    """The story's own plan; proposed before the scene contexts are created."""

    scene_context: list[SceneContext] = Field(default_factory=list)

    def set_story_plan(self, plan: StoryPlan) -> Self:
        self.story_plan = plan
        return self

    def set_scene_contexts(self, scenes: list[SceneContext]) -> Self:
        self.scene_context = scenes
        return self

    def add_scene_context(self, scene: SceneContext) -> Self:
        self.scene_context.append(scene)
        return self

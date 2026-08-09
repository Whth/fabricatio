from typing import Self

from pydantic import Field

from fabricatio_novel.models.context.base import ChainableContext, ContextBase
from fabricatio_novel.models.context.scene import SceneContext


class StoryContext(ChainableContext, ContextBase):
    scene_context: list[SceneContext] = Field(default_factory=list)

    def set_scene_contexts(self, scenes: list[SceneContext]) -> Self:
        self.scene_context = scenes
        return self

    def add_scene_context(self, scene: SceneContext) -> Self:
        self.scene_context.append(scene)
        return self

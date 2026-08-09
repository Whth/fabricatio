from typing import Generator, Self, final

from fabricatio_core.models.generic import Described, Titled
from pydantic import Field

from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.plan import StoryPlan


class StoryContext(Titled, Described, ContextBase):
    story_plan: StoryPlan | None = None
    """The story's own plan; proposed before the scene contexts are created."""

    scene_context: list[SceneContext] = Field(default_factory=list)

    @final
    def iter_scene_content(self) -> Generator[str, None, None]:
        """Yield each scene's composed content, in story order."""
        for scene_ctx in self.scene_context:
            if scene_ctx.content:
                yield scene_ctx.content

    def set_story_plan(self, plan: StoryPlan) -> Self:
        self.story_plan = plan
        return self

    def set_scene_contexts(self, scenes: list[SceneContext]) -> Self:
        self.scene_context = scenes
        return self

    def add_scene_context(self, scene: SceneContext) -> Self:
        self.scene_context.append(scene)
        return self

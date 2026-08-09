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

    @final
    def iter_child_contexts(self) -> Generator[SceneContext, None, None]:
        """Yield this story's scene contexts, in composition order."""
        yield from self.scene_context

    @final
    def iter_prefixed_contexts(self) -> Generator[SceneContext, None, None]:
        """Set each scene's running prefixed content in place and yield it.

        Composed content is read live at each step, so in-place updates made
        while iterating are reflected in the following scenes' prefixes.
        """
        prefix = self.prefixed_content
        for scene_ctx in self.scene_context:
            scene_ctx.set_prefixed_content(prefix)
            yield scene_ctx
            prefix = "\n\n".join(p for p in (prefix, scene_ctx.content) if p)

    def set_story_plan(self, plan: StoryPlan) -> Self:
        self.story_plan = plan
        return self

    def set_scene_contexts(self, scenes: list[SceneContext]) -> Self:
        self.scene_context = scenes
        return self

    def add_scene_context(self, scene: SceneContext) -> Self:
        self.scene_context.append(scene)
        return self

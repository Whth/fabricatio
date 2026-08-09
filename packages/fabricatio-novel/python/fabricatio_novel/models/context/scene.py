from typing import Self

from fabricatio_core.models.generic import Described, Titled

from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.plan import ScenePlan


class SceneContext(Titled, Described, ContextBase):
    scene_plan: ScenePlan | None = None
    """The scene's own plan."""

    content: str = ""
    previous_content: str = ""

    def set_scene_plan(self, plan: ScenePlan) -> Self:
        self.scene_plan = plan
        return self

    def set_content(self, content: str) -> Self:
        self.content = content
        return self

    def set_previous_content(self, previous_content: str) -> Self:
        self.previous_content = previous_content
        return self

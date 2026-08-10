from typing import ClassVar, Self

from fabricatio_core.models.generic import Described, Titled

from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.rag import RAGChannel
from fabricatio_novel.models.plan import ScenePlan


class SceneContext(RAGChannel, Titled, Described, ContextBase):
    heading_level: ClassVar[str] = "###"

    scene_plan: ScenePlan | None = None
    """The scene's own plan."""

    def set_scene_plan(self, plan: ScenePlan) -> Self:
        self.scene_plan = plan
        return self

from typing import Self, final

from fabricatio_core.models.generic import Described, Titled

from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.rag import RAGChannel
from fabricatio_novel.models.plan import ScenePlan


class SceneContext(RAGChannel, Titled, Described, ContextBase):
    content: str = ""
    """The composed prose of this scene; the only context level that owns composed content."""

    scene_plan: ScenePlan | None = None
    """The scene's own plan."""

    def set_scene_plan(self, plan: ScenePlan) -> Self:
        self.scene_plan = plan
        return self

    def set_content(self, content: str) -> Self:
        self.content = content
        return self

    @final
    def render_prefixed_block(self) -> str:
        """Render the scene's composed content; scene titles and descriptions are not injected."""
        return self.content

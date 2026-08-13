"""Pipeline channel model for a scene: its plan and the composed prose it writes."""

from typing import Self, final

from fabricatio_core.models.generic import Described, Titled

from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.rag import RAGChannel
from fabricatio_novel.models.plan import ScenePlan


class SceneContext(RAGChannel, Titled, Described, ContextBase):
    """A scene's composition channel: its plan and the composed prose it owns."""

    content: str = ""
    """The composed prose of this scene; the only context level that owns composed content."""

    scene_plan: ScenePlan | None = None
    """The scene's own plan."""

    def set_scene_plan(self, plan: ScenePlan) -> Self:
        """Set the scene's plan and return self."""
        self.scene_plan = plan
        return self

    @classmethod
    def from_plan(cls, plan: ScenePlan, expected_word_count: int) -> Self:
        """Build the scene context from its proposed plan."""
        return (
            cls(
                title=plan.title,
                description=plan.description,
                expected_word_count=expected_word_count,
            )
            .set_scene_plan(plan)
            .set_writing_style(plan.writing_style)
        )

    def set_content(self, content: str) -> Self:
        """Set the scene's composed prose and return self."""
        self.content = content
        return self

    @final
    def render_prefixed_block(self) -> str:
        """Render the scene's composed content; scene titles and descriptions are not injected."""
        return self.content

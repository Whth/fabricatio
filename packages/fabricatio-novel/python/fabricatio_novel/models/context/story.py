"""Pipeline channel model for a story: its plan and the scene contexts it writes."""

from typing import Generator, Self, final

from fabricatio_core.models.generic import Described, Titled
from pydantic import Field

from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.rag import RAGChannel
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.plan import StoryPlan
from fabricatio_novel.models.rag import WritingStyleDocument


class StoryContext(RAGChannel, Titled, Described, ContextBase):
    """A story's composition channel: its plan and the scene contexts it writes."""

    story_plan: StoryPlan | None = None
    """The story's own plan; proposed before the scene contexts are created."""

    scene_context: list[SceneContext] = Field(default_factory=list)

    style_docs: list[WritingStyleDocument] = Field(default_factory=list)
    """Writing style reference documents retrieved for this story; held to inform scene planning."""

    @classmethod
    def from_plan(cls, plan: StoryPlan, expected_word_count: int) -> Self:
        """Build the story context from its proposed plan."""
        return (
            cls(
                title=plan.title,
                description=plan.description,
                expected_word_count=expected_word_count,
            )
            .set_story_plan(plan)
            .set_writing_style(plan.writing_style)
        )

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
    def render_prefixed_block(self) -> str:
        """Render the scene blocks; the story's own title and description are not injected."""
        return "\n\n".join(child.render_prefixed_block() for child in self.iter_child_contexts())

    def set_story_plan(self, plan: StoryPlan) -> Self:
        """Set the story's plan and return self."""
        self.story_plan = plan
        return self

    def set_scene_contexts(self, scenes: list[SceneContext]) -> Self:
        """Replace the story's scene contexts and return self."""
        self.scene_context = scenes
        return self

    def add_scene_context(self, scene: SceneContext) -> Self:
        """Append a scene context to the story and return self."""
        self.scene_context.append(scene)
        return self

    def set_style_docs(self, docs: list[WritingStyleDocument]) -> Self:
        """Set the retrieved writing style references and return self."""
        self.style_docs = docs
        return self

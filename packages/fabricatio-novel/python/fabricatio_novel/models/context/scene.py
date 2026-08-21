"""Pipeline channel model for a scene: its plan and the composed prose it writes."""

from typing import Self, final

from fabricatio_core.models.generic import Described, Titled
from pydantic import Field

from fabricatio_novel.models.context.base import CharacterSpan, ContextBase
from fabricatio_novel.models.context.log import ContextEntry, ContextLog
from fabricatio_novel.models.plan import ScenePlan


class SceneContext(Titled, Described, ContextBase):
    """A scene's composition channel: its plan and the composed prose it owns."""

    content: str = ""
    """The composed prose of this scene; the only context level that owns composed content."""

    scenes_log: ContextLog = Field(default_factory=ContextLog)
    """The story's composed scenes before this one, as an append-only log; rendered after the style references."""

    style_docs: list[str] = Field(default_factory=list)
    """Rendered writing style reference texts broadcast from the story; injected raw into the write prompt."""

    scene_plan: ScenePlan | None = None
    """The scene's own plan."""

    charactor_span: list[CharacterSpan] = Field(default_factory=list)
    """The story's character spans broadcast to this scene for prompt rendering; prompt-only clone, no slice."""

    def set_scene_plan(self, plan: ScenePlan) -> Self:
        """Set the scene's own plan and return self."""
        self.scene_plan = plan
        return self

    def set_scenes_log(self, scenes_log: ContextLog) -> Self:
        """Set the story-scoped log of the scenes preceding this one and return self."""
        self.scenes_log = scenes_log
        return self

    def set_style_docs(self, docs: list[str]) -> Self:
        """Set the rendered writing style reference texts and return self."""
        self.style_docs = docs
        return self

    def set_charactor_spans(self, spans: list[CharacterSpan]) -> Self:
        """Replace this scene's character spans and return self."""
        self.charactor_span = spans
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
            .set_cast(plan.cast)
        )

    def set_content(self, content: str) -> Self:
        """Set the scene's composed prose and return self."""
        self.content = content
        return self

    def dump_characters(self) -> str:
        """Render this scene's broadcast character spans for its writing prompt."""
        return "\n\n".join(span.dump_to_prompt() for span in self.charactor_span)

    @final
    def prefixed_entries(self) -> tuple[ContextEntry, ...]:
        """Contribute the composed content; scene titles and descriptions are not injected."""
        if not self.content:
            return ()
        return (ContextEntry(kind="scene_content", title=self.title, body=self.content),)

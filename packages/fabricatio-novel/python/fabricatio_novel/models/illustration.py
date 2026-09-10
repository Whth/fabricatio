"""Illustration models: the illustrated scene output and per-role settings.

The propose-able generation instruction for scene illustrations is the
ComfyUI :class:`~fabricatio_comfyui.models.specs.SketchSpec` (positive
prompt, negative prompt, and canvas); the models below carry the rendered
result, the resolved render unit, and the scoped settings.
"""

import html
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Self

from fabricatio_comfyui.models import LoraCatalog, LoraEntry, LoraSpec
from fabricatio_comfyui.models.specs import SketchSpec
from fabricatio_core.models.generic import ScopedConfig

from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.scene import Scene
from fabricatio_novel.utils import scene_image_name

__all__ = [
    "IllustratedScene",
    "IllustrationPromptDecorator",
    "IllustrationScopedConfig",
    "RenderError",
    "RenderJob",
    "RenderOutcome",
]


class IllustrationScopedConfig(ScopedConfig):
    """Per-instance illustration settings with hierarchical fallback.

    Fields default to ``None`` (unset at this scope) and resolve through
    the framework's scoped-config chain: a per-call argument wins, then
    this instance's field, then the global
    :data:`fabricatio_novel.config.novel_config`.  Roles compose this
    class through :class:`~fabricatio_novel.capabilities.illustration.IllustrateScenes`
    and propagate their values to workflows and steps via
    :meth:`hold_to` / :meth:`fallback_to`.
    """

    illustration_constraint: str | None = None
    """Global style/content constraint merged into every illustration prompt proposal.

    Used by :meth:`IllustrateScenes.illustrate_novel_phase` when no per-call
    ``illustration_constraint`` is given; falls back to the global
    ``[ext.novel] illustration_constraint``.
    """

    illustration_choose_loras: bool | None = None
    """Per-instance opt-in for catalog LoRA selection; ``None`` falls back to the global
    ``[ext.novel] illustration_choose_loras``."""

    illustration_judge: bool | None = None
    """Per-instance opt-in for visual illustration judgement; ``None`` falls back to the
    global ``[ext.novel] illustration_judge``."""


class IllustratedScene(Scene):
    """A composed scene carrying its rendered illustration."""

    illustration_prompt: str = ""
    """The image-generation prompt proposed for this scene; empty until illustrated."""

    illustration_image: str = ""
    """Absolute path of the rendered illustration PNG; empty until illustrated."""

    @classmethod
    def from_context(
        cls,
        ctx: SceneContext,
        *,
        illustration_prompt: str = "",
        illustration_image: str = "",
    ) -> Self:
        """Materialize an illustrated scene from its context, recording the rendered illustration."""
        return cls(
            title=ctx.title,
            description=ctx.description,
            expected_word_count=ctx.expected_word_count,
            writing_styles=list(ctx.plan.writing_styles) if ctx.plan is not None else [],
            writing_constraints=list(ctx.writing_constraints),
            content=ctx.content,
            illustration_prompt=illustration_prompt,
            illustration_image=illustration_image,
        )

    def to_xhtml(self, chapter_index: int, scene_index: int) -> str:
        """Render the scene's paragraphs followed by its illustration figure."""
        sections = [super().to_xhtml(chapter_index, scene_index)]
        if self.illustration_image:
            sections.append(
                f'<figure class="illustration"><img src="images/{scene_image_name(chapter_index, scene_index)}" '
                f'alt="{html.escape(self.title)}"/></figure>'
            )
        return "\n".join(sections)

    def epub_resources(self, chapter_index: int, scene_index: int) -> list[tuple[str, Path]]:
        """Return this scene's illustration as an EPUB image resource, or nothing before one exists."""
        if not self.illustration_image:
            return []
        return [(f"images/{scene_image_name(chapter_index, scene_index)}", Path(self.illustration_image))]


@dataclass(frozen=True)
class IllustrationPromptDecorator:
    """Final render-prompt rule shared by a whole render batch.

    Closes every prompt the same way: always-on lora trigger words first,
    then the picked loras' trigger words resolved from the catalog, then
    the configured quality-tag suffix — so the initial render and every
    judged re-render of a scene ship the identical decoration rule.
    """

    always: tuple[LoraEntry, ...]
    """``illustration_always_loras`` entries riding every render of the batch."""

    catalog: LoraCatalog
    """Selectable lora pool resolving picked trigger words."""

    suffix: str
    """``illustration_prompt_suffix`` appended to the decorated prompt; empty appends nothing."""

    def __call__(self, base: str, picked: Sequence[LoraSpec]) -> str:
        """Decorate a proposed prompt into the final render prompt."""
        prompt = base
        for entry in self.always:
            prompt = entry.augmented_prompt(prompt)
        prompt = self.catalog.augment(prompt, list(picked))
        return f"{prompt},{self.suffix}" if self.suffix else prompt

    def always_specs(self) -> tuple[LoraSpec, ...]:
        """The always-on loras as render-chain specs."""
        return tuple(LoraSpec(lora_name=e.lora_name, strength=e.strength) for e in self.always)


@dataclass(frozen=True)
class RenderOutcome:
    """One completed render: the final prompt sent and the canonical image path."""

    prompt: str
    """The decorated prompt that produced the image."""

    image: str
    """Absolute path of the canonical PNG."""


class RenderError(Exception):
    """One scene's render failed; propagates through the refine loop and degrades the scene where caught."""


@dataclass(frozen=True)
class RenderJob:
    """One scene's fully-resolved render unit: spec, final prompt, and lora chain."""

    key: tuple[int, int]
    """``(chapter_index, scene_index)`` of the scene; indices match the EPUB exporter naming."""

    title: str
    """Scene title, used in per-scene logging."""

    spec: SketchSpec
    """The proposed sketch spec this job renders."""

    target: Path
    """Path of the canonical PNG inside the run's ``images/`` directory."""

    requirement: str
    """Rendered proposal requirement; revisions append their feedback tail to it."""

    prompt: str
    """Final decorated render prompt of ``spec``."""

    loras: tuple[LoraSpec, ...]
    """Full render chain: always-on loras then the picked ones."""

    picked: tuple[LoraSpec, ...]
    """The per-scene picked loras; retries keep this chain frozen."""

    decorator: IllustrationPromptDecorator
    """Batch decoration rule re-deriving the prompt from any revised spec."""

    def with_spec(self, spec: SketchSpec) -> Self:
        """Return the job re-resolved for a revised spec under the same lora chain."""
        return replace(self, spec=spec, prompt=self.decorator(spec.prompt, self.picked))

    def archive_path(self, attempt: int) -> Path:
        """Rejected-attempt archive path beside the canonical target."""
        return self.target.with_name(f"{self.target.stem}.attempt{attempt}{self.target.suffix}")

    def entry_of(self, outcome: RenderOutcome) -> tuple[tuple[int, int], tuple[str, str]]:
        """Map a render outcome to its illustrations-map entry."""
        return (self.key, (outcome.prompt, outcome.image))

"""Scene composition capabilities: rendering requirements and generating scene content."""

from abc import ABC
from typing import Unpack

from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK, word_count
from fabricatio_core.utils import ok

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.scene import Scene
from fabricatio_novel.utils import strip_overlapping_prefix


class SceneCompose(CharacterCompose, ABC):
    """This class contains the capabilities for the scene."""

    async def before_compose_scene_context(
        self,
        ctx: SceneContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> SceneContext:
        """Identity hook invoked before composing a scene; may mutate the context."""
        return ctx

    async def after_compose_scene_context(
        self,
        ctx: SceneContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> SceneContext:
        """Identity hook invoked after generating a scene; may mutate the context."""
        return ctx

    async def post_process_scene(self, ctx: SceneContext, scene: Scene, **kwargs: Unpack[LLMKwargs]) -> Scene:
        """Identity hook invoked on the composed scene; may transform and return the scene."""
        return scene

    def _scene_requirement_vars(self, ctx: SceneContext) -> dict[str, object]:
        """Build the scene_requirement template variables for a scene context.

        Overriding capabilities (RAG) reuse these vars and add their own
        blocks before rendering. The setting bible arrives through the
        seeded prefix entry, not as a dedicated template variable.
        """
        return {
            "title": ctx.title,
            "description": ctx.description,
            "expected_word_count": ctx.expected_word_count,
            "writing_styles": ctx.writing_styles,
            "writing_constraints": ctx.writing_constraints,
            "characters": ctx.dump_characters(),
            "cast": ctx.cast,
            "language": ctx.language,
            "novel_so_far": ctx.prefix_log.render(),
        }

    async def prepare_scene_requirement(
        self,
        ctx: SceneContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
        """Render the scene requirement prompt from the scene context.

        Overriding capabilities may extend the rendered requirement, for
        example by appending writing style references.
        """
        return TEMPLATE_MANAGER.render_template(
            novel_config.scene_requirement_template,
            self._scene_requirement_vars(ctx),
        )

    async def generate_scene_context(
        self,
        ctx: SceneContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> SceneContext:
        """Generate the scene content via the LLM.

        Renders the scene requirement, asks the LLM for the scene text, and
        stores the content on the context. Returns the composed context.
        """
        logger.debug(f"Generating scene '{ctx.title}'")
        requirement = await self.prepare_scene_requirement(ctx, **kwargs)
        logger.debug(f"Scene '{ctx.title}' requirement rendered ({len(requirement)} chars)")
        content = ok(await self.ageneric_string(requirement, send_to=send_to, **kwargs))
        previous = "\n".join(entry.body for entry in ctx.prefix_log.entries if entry.kind == "scene_content")
        content = strip_overlapping_prefix(
            content,
            previous,
            min_chars=novel_config.scene_overlap_min_chars,
            max_ratio=novel_config.scene_overlap_max_ratio,
        )
        ctx.set_content(content)
        return ctx

    async def prepare_story(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> None:
        """Prepare the story before its scenes are planned.

        Identity hook; retrieval capabilities (e.g. RAG) override it to
        gather style references held on the story context for planning.
        """

    async def compose_scene(
        self,
        ctx: SceneContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Scene | None:
        """Compose a scene end to end: before, generate, after, then post-process; returns None when generation fails."""
        ctx = await self.before_compose_scene_context(ctx, **kwargs)
        ctx = await self.generate_scene_context(ctx, send_to, **kwargs)
        ctx = await self.after_compose_scene_context(ctx, **kwargs)

        scene = Scene.from_context(ctx)
        logger.info(
            f"Scene '{scene.title}' composed ({word_count(scene.content)} words, word count satisfaction: {scene.satisfy_ratio()}",
        )
        return await self.post_process_scene(ctx, scene, **kwargs)

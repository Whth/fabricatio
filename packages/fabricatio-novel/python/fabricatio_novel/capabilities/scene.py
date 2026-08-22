"""Scene composition capabilities: rendering requirements and generating scene content."""

from abc import ABC
from typing import Unpack

from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK, detect_language, word_count

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.scene import Scene


class SceneCompose(CharacterCompose, ABC):
    """This class contains the capabilities for the scene."""

    async def before_compose_scene(
        self,
        ctx: SceneContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> SceneContext:
        """Identity hook invoked before composing a scene; may mutate the context."""
        return ctx

    async def after_compose_scene(
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
        characters = ctx.dump_characters()
        return {
            "title": ctx.title,
            "description": ctx.description,
            "expected_word_count": ctx.expected_word_count,
            "writing_styles": ctx.dump_writing_styles(),
            "scene_style": ctx.scene_plan.writing_style if ctx.scene_plan is not None else "",
            "writing_constraint": ctx.writing_constraint,
            "characters": characters,
            "cast": ", ".join(ctx.cast),
            "language": ctx.language or detect_language(ctx.description),
            "prefixed_content": ctx.prefix_log.render(),
            "scenes_so_far": ctx.scenes_log.render(),
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

    async def generate_scene(
        self,
        ctx: SceneContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Scene | None:
        """Generate the scene content via the LLM.

        Renders the scene requirement, asks the LLM for the scene text, sets
        the expected word count, and stores the content on the context.
        Returns the generated scene.
        """
        logger.debug(f"Generating scene '{ctx.title}'")
        requirement = await self.prepare_scene_requirement(ctx, **kwargs)
        logger.debug(f"Scene '{ctx.title}' requirement rendered ({len(requirement)} chars)")
        scene = Scene(
            title=ctx.title,
            description=ctx.description,
            expected_word_count=0,
            content=(await self.aask(requirement, send_to=send_to, **kwargs)).strip(),
        )
        scene.expect_(ctx.expected_word_count)
        ctx.set_content(scene.content)
        logger.info(
            f"Scene '{scene.title}' composed ({word_count(scene.content)} words, word count satisfaction: {scene.satisfy_ratio()}"
        )
        return scene

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
        ctx = await self.before_compose_scene(ctx, **kwargs)
        scene = await self.generate_scene(ctx, send_to, **kwargs)
        ctx = await self.after_compose_scene(ctx, **kwargs)

        if scene is None:
            return None
        return await self.post_process_scene(ctx, scene, **kwargs)

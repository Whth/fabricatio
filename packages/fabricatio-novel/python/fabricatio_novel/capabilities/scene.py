"""Scene composition capabilities: rendering requirements and generating scene content."""

from abc import ABC
from typing import Unpack

from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK, word_count

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.scene import Scene
from fabricatio_novel.utils import strip_overlapping_prefix


class SceneCompose[CTX: SceneContext](CharacterCompose, ABC):
    """This class contains the capabilities for the scene."""

    async def before_compose_scene_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Identity hook invoked before composing a scene; may mutate the context.

        ``send_to`` is the routing group the run's calls use, so a hook that reaches
        the model on its own routes it like the rest of the run.
        """
        return ctx

    async def after_compose_scene_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Identity hook invoked after generating a scene; may mutate the context.

        ``send_to`` is the routing group the run's calls use, so a hook that reaches
        the model on its own routes it like the rest of the run.
        """
        return ctx

    async def post_process_scene(self, ctx: SceneContext, scene: Scene, **kwargs: Unpack[LLMKwargs]) -> Scene:
        """Identity hook invoked on the composed scene; may transform and return the scene."""
        return scene

    async def prepare_scene_requirement(
        self,
        ctx: CTX,
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
        """Render the scene requirement prompt from the scene context.

        Overriding capabilities may extend the rendered requirement, for
        example by appending writing style references. The chapter-opening flag
        comes off the context's prefix log, so the prompt can say when this
        scene starts its chapter instead of continuing the text above it.
        """
        return TEMPLATE_MANAGER.render_template(
            novel_config.scene_requirement_template,
            {
                "title": ctx.title,
                "description": ctx.description,
                "expected_word_count": ctx.expected_word_count,
                "writing_styles": ctx.writing_styles,
                "writing_constraints": ctx.writing_constraints,
                "characters": ctx.dump_characters(),
                "cast": ctx.cast,
                "language": ctx.language,
                "skills": ctx.skill_section(),
                "novel_so_far": ctx.prefix_log.render(),
                "chapter_opening": ctx.is_chapter_opening(),
            },
        )

    async def generate_scene_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Generate the scene content via the LLM.

        Renders the scene requirement, asks the LLM for the scene text, and
        stores the content on the context. Returns the composed context.

        Raises:
            ValueError: the model returned no prose; an empty scene would be
                serialized into the chapter, the export and the EPUB unnoticed.
        """
        logger.debug(f"Generating scene '{ctx.title}'")
        requirement = await self.prepare_scene_requirement(ctx, **kwargs)
        logger.debug(f"Scene '{ctx.title}' requirement rendered ({len(requirement)} chars)")

        content = await self.aask(requirement, send_to=send_to, **kwargs)

        previous = "\n".join(entry.body for entry in ctx.prefix_log.entries if entry.kind.is_scene_content())
        content = strip_overlapping_prefix(
            content,
            previous,
            min_chars=novel_config.scene_overlap_min_chars,
            max_ratio=novel_config.scene_overlap_max_ratio,
        )
        if not content.strip():
            raise ValueError(f"Scene '{ctx.title}' produced no prose; empty scenes are never serialized")

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
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Scene | None:
        """Compose a scene end to end: before, generate, after, then post-process; returns None when generation fails."""
        ctx = await self.before_compose_scene_context(ctx, send_to=send_to, **kwargs)
        ctx = await self.generate_scene_context(ctx, send_to, **kwargs)
        ctx = await self.after_compose_scene_context(ctx, send_to=send_to, **kwargs)

        scene = Scene.from_context(ctx)
        logger.info(
            f"Scene '{scene.title}' composed ({word_count(scene.content)} words, word count satisfaction: {scene.satisfy_ratio()}",
        )
        return await self.post_process_scene(ctx, scene, **kwargs)

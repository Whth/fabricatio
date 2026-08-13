"""Story composition capabilities: planning scenes and composing stories."""

from abc import ABC
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK

from fabricatio_novel.capabilities.scene import SceneCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import ScenePlan, ScenePlans
from fabricatio_novel.models.story import Story


class StoryCompose(SceneCompose, ABC):
    """This class contains the capabilities for the story."""

    async def before_compose_story(
        self,
        ctx: StoryContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> StoryContext:
        """Identity hook invoked before composing a story; may mutate the context."""
        return ctx

    async def after_compose_story(
        self,
        ctx: StoryContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> StoryContext:
        """Identity hook invoked after generating a story; may mutate the context."""
        return ctx

    async def post_process_story(self, ctx: StoryContext, story: Story, **kwargs: Unpack[LLMKwargs]) -> Story:
        """Identity hook invoked on the composed story; may transform and return the story."""
        return story

    async def plan_scenes(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[ScenePlan] | None:
        """Propose scene plans for the story via the LLM.

        Renders the scene plan template from the story context and proposes
        a ScenePlans batch, returning the root list of plans or None on failure.
        """
        logger.debug(f"Planning scenes for story '{ctx.title}'")
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.scene_plan_template,
            {
                "title": ctx.title,
                "description": ctx.description,
                "expected_word_count": ctx.expected_word_count,
                "language": ctx.language,
                "characters": ctx.dump_charactors(),
            },
        )
        plans = await self.propose(ScenePlans, requirement, send_to=send_to, **kwargs)
        return plans.root if plans is not None else None

    async def generate_story(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Story | None:
        """Generate the story by composing its scenes.

        Interpolates character states, plans scenes (with word counts
        allocated by weight) when none are scheduled, broadcasts the settings
        bible, splits character slices per scene, and composes each scene in
        prefix order. Returns the materialized story or None when planning
        or any scene composition fails.
        """
        logger.debug(f"Generating story '{ctx.title}'")
        await self.interpolate_characters(ctx, send_to, **kwargs)
        if not ctx.scene_context:
            scene_plans = await self.plan_scenes(ctx, send_to, **kwargs)
            if scene_plans is None:
                return None
            counts = ctx.allocate([s.weight for s in scene_plans]) if scene_plans else []
            for scene_plan, count in zip(scene_plans, counts, strict=True):
                ctx.add_scene_context(
                    SceneContext.from_plan(scene_plan, expected_word_count=count)
                    .set_language(ctx.language)
                    .set_rag_query(ctx.rag_query)
                    .set_rag_limit(ctx.rag_limit)
                )
            logger.info(f"Planned {len(ctx.scene_context)} scene(s) for story '{ctx.title}'")
        ctx.broadcast_settings_bible()
        await self.split_character_slices(ctx, ctx.scene_context, send_to, **kwargs)
        for scene_ctx in ctx.iter_prefixed_contexts():
            if await self.compose_scene(scene_ctx, send_to, **kwargs) is None:
                return None
        return Story.from_context(ctx)

    async def compose_story(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Story | None:
        """Compose a story end to end: before, generate, after, then post-process; returns None when generation fails."""
        ctx = await self.before_compose_story(ctx, **kwargs)
        story = await self.generate_story(ctx, send_to, **kwargs)
        ctx = await self.after_compose_story(ctx, **kwargs)

        if story is None:
            return None
        return await self.post_process_story(ctx, story, **kwargs)

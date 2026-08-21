"""Story composition capabilities: planning scenes and composing stories."""

from abc import ABC
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK

from fabricatio_novel.capabilities.scene import SceneCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.base import merge_writing_constraints
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
                "outline": ctx.outline,
                "title": ctx.title,
                "description": ctx.description,
                "expected_word_count": ctx.expected_word_count,
                "writing_styles": ctx.dump_writing_styles(),
                "writing_constraint": ctx.writing_constraint,
                "language": ctx.language,
                "characters": ctx.dump_characters(),
                "cast": ", ".join(ctx.cast),
            },
        )
        plans = await self.propose(ScenePlans, requirement, send_to=send_to, **kwargs)
        return plans.root if plans is not None else None

    async def plan_scenes_phase(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Retrieve story references and plan its scenes.

        Scene plans are materialized with word counts allocated by weight
        when none are scheduled.

        Returns:
            bool: True when the scenes are planned; False on planning failure.
        """
        await self.prepare_story(ctx, send_to, **kwargs)
        if not ctx.scene_context:
            scene_plans = await self.plan_scenes(ctx, send_to, **kwargs)
            if scene_plans is None:
                logger.error(f"Scene planning failed for story '{ctx.title}'; aborting story generation")
                return False
            counts = ctx.allocate([s.weight for s in scene_plans]) if scene_plans else []
            for scene_plan, count in zip(scene_plans, counts, strict=True):
                ctx.add_scene_context(
                    SceneContext.from_plan(scene_plan, expected_word_count=count)
                    .set_language(ctx.language)
                    .set_outline(ctx.outline)
                    .set_writing_styles(list(ctx.writing_styles))
                    .set_writing_constraint(
                        merge_writing_constraints(ctx.writing_constraint, scene_plan.writing_constraint)
                    )
                )
            logger.info(f"Planned {len(ctx.scene_context)} scene(s) for story '{ctx.title}'")
        return True

    async def prepare_scene_write(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> None:
        """Broadcast the bible and the story's character spans to every scene before the write."""
        ctx.broadcast_settings_bible()
        for scene_ctx in ctx.scene_context:
            scene_ctx.set_charactor_spans(ctx.charactor_span)

    async def compose_scenes_phase(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Compose every scene serially in prefix order.

        Each scene's prefix log is the story's own prefix (everything composed
        before the story, constant across its scenes) while the story's earlier
        scenes accumulate in a separate story-scoped log, so stable content like
        style references can sit between them for prefix-cache reuse. Every scene
        receives a branch of the story-scoped log taken before its own
        composition, so a scene never sees itself or any later sibling.

        Returns:
            bool: True when every scene composed; False on any failure.
        """
        total = len(ctx.scene_context)
        for i, scene_ctx in enumerate(ctx.scene_context, start=1):
            scene_ctx.set_prefix_log(ctx.prefix_log).set_scenes_log(ctx.scenes_log.branch())
            logger.info(f"Composing scene {i}/{total} '{scene_ctx.title}'")
            if await self.compose_scene(scene_ctx, send_to, **kwargs) is None:
                logger.error(f"Scene '{scene_ctx.title}' failed; aborting story '{ctx.title}'")
                return False
            ctx.scenes_log = ctx.scenes_log.with_entries(scene_ctx.prefixed_entries())
        return True

    async def generate_story(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Story | None:
        """Generate the story by composing its scenes.

        Runs the staged phases in order: scene planning, scene write
        preparation, serial scene composition, and story assembly. Returns
        the materialized story or None when any phase fails.
        """
        logger.debug(f"Generating story '{ctx.title}'")
        if not await self.plan_scenes_phase(ctx, send_to, **kwargs):
            return None
        await self.prepare_scene_write(ctx, send_to, **kwargs)
        if not await self.compose_scenes_phase(ctx, send_to, **kwargs):
            return None
        story = Story.from_context(ctx)
        logger.info(
            f"Story '{story.title}' composed ({len(story.scenes)} scene(s),  word count satisfaction: {story.satisfy_ratio()}"
        )
        return story

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

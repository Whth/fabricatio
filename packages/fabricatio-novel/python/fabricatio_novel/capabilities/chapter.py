"""Chapter composition capabilities: planning stories and composing chapters."""

from abc import ABC
from typing import Unpack

from fabricatio_character.models.character import CharacterCardBoundaries
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_core.utils import ok

from fabricatio_novel.capabilities.story import StoryCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.chapter import Chapter
from fabricatio_novel.models.context.base import (
    stitch_boundaries,
)
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import StoryPlan, StoryPlans


class ChapterCompose[CTX: ChapterContext, S: StoryContext](StoryCompose[S], ABC):
    """This class contains the capabilities for the chapter."""

    async def before_compose_chapter_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Identity hook invoked before composing a chapter; may mutate the context.

        ``send_to`` is the routing group the run's calls use, so a hook that reaches
        the model on its own routes it like the rest of the run.
        """
        return ctx

    async def after_compose_chapter_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Identity hook invoked after generating a chapter; may mutate the context.

        ``send_to`` is the routing group the run's calls use, so a hook that reaches
        the model on its own routes it like the rest of the run.
        """
        return ctx

    async def post_process_chapter(self, ctx: ChapterContext, chapter: Chapter, **kwargs: Unpack[LLMKwargs]) -> Chapter:
        """Identity hook invoked on the composed chapter; may transform and return the chapter."""
        return chapter

    async def plan_stories(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[StoryPlan] | None:
        """Propose story plans for the chapter via the LLM.

        Renders the plan requirement template from the chapter context and proposes
        a StoryPlans batch, returning the root list of plans or None on failure.
        """
        logger.debug(f"Planning stories for chapter '{ctx.title}'")
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.plan_requirement_template,
            {
                "outline": ctx.outline,
                "planning_title": "Story Planning",
                "goal": f"A Chapter is consist of Story obj(s), which you need to make for the chapter `{ctx.title}` now",
                "parent_title": "Chapter",
                "cast_title": "Chapter Cast",
                "title": ctx.title,
                "description": ctx.description,
                "expected_word_count": ctx.expected_word_count,
                "writing_styles": ctx.writing_styles,
                "writing_constraints": ctx.writing_constraints,
                "skills": ctx.skill_section(),
                "language": ctx.language,
                "characters": ctx.dump_characters(),
                "cast": ctx.cast,
            },
        )
        plans = await self.propose(StoryPlans, requirement, send_to=send_to, **kwargs)
        return plans.root if plans is not None else None

    async def draft_story_spans(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> None:
        """Draft the S-1 story-boundary cards per character in a single LLM batch.

        The chapter spans already fix the endpoints: the first story starts
        at the chapter's start card and the last story ends at the chapter's
        end card. Only the boundaries between consecutive stories are
        proposed; the spans are stitched in code so the chain is continuous
        by construction. Skipped silently when the chapter has no character
        spans or no stories, so tests and runs without a roster pass through
        unchanged. A single story inherits the chapter's spans directly
        without any LLM call.
        """
        if not ctx.charactor_span or not ctx.child_contexts:
            return
        if len(ctx.child_contexts) == 1:
            ctx.child_contexts[0].set_charactor_spans(ctx.charactor_span)
            logger.debug(f"Single story inherits chapter '{ctx.title}' spans")
            return
        logger.debug(f"Drafting {len(ctx.child_contexts) - 1} story boundary card(s) per character")
        proposed = ok(
            await self.propose(
                CharacterCardBoundaries,
                TEMPLATE_MANAGER.render_template(
                    novel_config.boundary_requirement_template,
                    {
                        "skills": ctx.skill_section(),
                        "drafting_title": "Story Character Boundary Drafting",
                        "endpoint_source": "chapter spans",
                        "parent_title": "Chapter",
                        "title": ctx.title,
                        "description": ctx.description,
                        "spans_title": "Chapter Spans (parent arc)",
                        "spans": ctx.dump_characters(),
                        "children_title": "Stories (in order)",
                        "children": [{"title": s.title, "description": s.description} for s in ctx.child_contexts],
                        "boundary_letter": "S",
                        "unit_singular": "story",
                        "unit_plural": "stories",
                        "card_prefix": "chapter",
                        "arc_noun": "chapter",
                        "language": ctx.language,
                    },
                ),
                send_to=send_to,
                **kwargs,
            ),
        )
        stitch_boundaries(
            ctx.charactor_span,
            ctx.child_contexts,
            lambda story_ctx: story_ctx.charactor_span,
            proposed.root,
            len(ctx.child_contexts) - 1,
            "story",
        )

    async def plan_stories_phase(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Plan stories when none are scheduled and draft their character spans.

        Returns:
            bool: True when the stories are planned; False on planning failure.
        """
        if not ctx.child_contexts:
            story_plans = await self.plan_stories(ctx, send_to, **kwargs)
            if story_plans is None:
                logger.error(f"Story planning failed for chapter '{ctx.title}'; aborting chapter generation")
                return False
            counts = ctx.allocate([s.weight for s in story_plans]) if story_plans else []
            for story_plan, count in zip(story_plans, counts, strict=True):
                ctx.add_context(
                    StoryContext.create(ctx.outline, language=ctx.language)
                    .update_from(story_plan)
                    .set_plan(story_plan)
                    .expect_(count)
                    .set_writing_styles([*ctx.writing_styles, *story_plan.writing_styles])
                    .set_writing_constraints(story_plan.writing_constraints)
                    .with_skills_from(ctx),
                )
            logger.info(f"Planned {len(ctx.child_contexts)} story(s) for chapter '{ctx.title}'")
        await self.draft_story_spans(ctx, send_to, **kwargs)
        return True

    async def compose_stories_phase(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Compose every story in prefix order.

        Returns:
            bool: True when every story composed; False on any failure.
        """
        total = len(ctx.child_contexts)
        for i, story_ctx in enumerate(ctx.iter_prefixed_contexts(), start=1):
            logger.info(f"Composing story {i}/{total} '{story_ctx.title}'")
            if await self.compose_story(story_ctx, send_to, **kwargs) is None:
                logger.error(f"Story '{story_ctx.title}' failed; aborting chapter '{ctx.title}'")
                return False
        return True

    async def generate_chapter_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX | None:
        """Generate the chapter by composing its stories.

        Runs the staged phases in order: story planning and story
        composition. Returns the composed context or None when any phase
        fails.
        """
        logger.debug(f"Generating chapter '{ctx.title}'")
        if not await self.plan_stories_phase(ctx, send_to, **kwargs):
            return None
        if not await self.compose_stories_phase(ctx, send_to, **kwargs):
            return None
        return ctx

    async def compose_chapter(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Chapter | None:
        """Compose a chapter end to end: before, generate, after, then post-process; returns None when generation fails."""
        ctx = await self.before_compose_chapter_context(ctx, send_to=send_to, **kwargs)
        ctx_res = await self.generate_chapter_context(ctx, send_to, **kwargs)
        if ctx_res is None:
            return None
        ctx = ctx_res
        ctx = await self.after_compose_chapter_context(ctx, send_to=send_to, **kwargs)

        chapter = Chapter.from_context(ctx)
        logger.info(
            f"Chapter '{chapter.title}' composed ({len(chapter.story)} story(s),  word count satisfaction: {chapter.satisfy_ratio()}",
        )
        return await self.post_process_chapter(ctx, chapter, **kwargs)

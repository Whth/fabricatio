"""Chapter composition capabilities: planning stories and composing chapters."""

from abc import ABC
from typing import Callable, Sequence, Unpack

from fabricatio_character.models.character import CharacterCard, CharacterCardBoundaries
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_core.utils import ok

from fabricatio_novel.capabilities.story import StoryCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.chapter import Chapter
from fabricatio_novel.models.context.base import (
    CharacterSpan,
    derive_child_spans,
    merge_writing_constraints,
)
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import StoryPlan, StoryPlans


class ChapterCompose(StoryCompose, ABC):
    """This class contains the capabilities for the chapter."""

    async def before_compose_chapter(
        self,
        ctx: ChapterContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> ChapterContext:
        """Identity hook invoked before composing a chapter; may mutate the context."""
        return ctx

    async def after_compose_chapter(
        self,
        ctx: ChapterContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> ChapterContext:
        """Identity hook invoked after generating a chapter; may mutate the context."""
        return ctx

    async def post_process_chapter(self, ctx: ChapterContext, chapter: Chapter, **kwargs: Unpack[LLMKwargs]) -> Chapter:
        """Identity hook invoked on the composed chapter; may transform and return the chapter."""
        return chapter

    async def plan_stories(
        self,
        ctx: ChapterContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[StoryPlan] | None:
        """Propose story plans for the chapter via the LLM.

        Renders the story plan template from the chapter context and proposes
        a StoryPlans batch, returning the root list of plans or None on failure.
        """
        logger.debug(f"Planning stories for chapter '{ctx.title}'")
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.story_plan_template,
            {
                "title": ctx.title,
                "description": ctx.description,
                "expected_word_count": ctx.expected_word_count,
                "writing_style": ctx.writing_style,
                "writing_constraint": ctx.writing_constraint,
                "language": ctx.language,
                "characters": ctx.dump_characters(),
                "cast": ", ".join(ctx.cast),
            },
        )
        plans = await self.propose(StoryPlans, requirement, send_to=send_to, **kwargs)
        return plans.root if plans is not None else None

    async def draft_story_spans(
        self,
        ctx: ChapterContext,
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
        if not ctx.charactor_span or not ctx.story_context:
            return
        if len(ctx.story_context) == 1:
            ctx.story_context[0].set_charactor_spans(ctx.charactor_span)
            logger.debug(f"Single story inherits chapter '{ctx.title}' spans")
            return
        logger.debug(f"Drafting {len(ctx.story_context) - 1} story boundary card(s) per character")
        proposed = ok(
            await self.propose(
                CharacterCardBoundaries,
                TEMPLATE_MANAGER.render_template(
                    novel_config.story_character_span_template,
                    {
                        "chapter_title": ctx.title,
                        "chapter_description": ctx.description,
                        "language": ctx.language,
                        "chapter_spans": ctx.dump_characters(),
                        "stories": [{"title": s.title, "description": s.description} for s in ctx.story_context],
                    },
                ),
                send_to=send_to,
                **kwargs,
            )
        )
        self._stitch_boundaries(
            ctx.charactor_span,
            ctx.story_context,
            lambda story_ctx: story_ctx.charactor_span,
            proposed.root,
            len(ctx.story_context) - 1,
            "story",
        )

    def _stitch_boundaries[C](
        self,
        parent_spans: list[CharacterSpan],
        children: Sequence[C],
        spans_accessor: Callable[[C], list[CharacterSpan]],
        proposed: list[list[CharacterCard]],
        expected_boundaries: int,
        level: str,
    ) -> None:
        """Stitch one child span per element from the parent spans and proposed boundaries.

        For every roster character the parent span opens the first child and
        closes the last; the proposed boundary cards are the intermediate
        states. A character whose boundary count does not match the expected
        number is skipped so a malformed proposal never yields a broken
        chain.
        """
        for char_index, parent_span in enumerate(parent_spans):
            boundaries = proposed[char_index] if char_index < len(proposed) else []
            if len(boundaries) != expected_boundaries:
                logger.warn(
                    f"Expected {expected_boundaries} {level} boundary card(s) for '{parent_span.start.name}'"
                    f" but got {len(boundaries)}; skipping"
                )
                continue
            for child, span in zip(children, derive_child_spans(parent_span, boundaries), strict=True):
                spans_accessor(child).append(span)
        logger.debug(f"Stitched {level} spans from boundary cards")

    async def plan_stories_phase(
        self,
        ctx: ChapterContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Plan stories when none are scheduled and draft their character spans.

        Returns:
            bool: True when the stories are planned; False on planning failure.
        """
        if not ctx.story_context:
            story_plans = await self.plan_stories(ctx, send_to, **kwargs)
            if story_plans is None:
                logger.error(f"Story planning failed for chapter '{ctx.title}'; aborting chapter generation")
                return False
            counts = ctx.allocate([s.weight for s in story_plans]) if story_plans else []
            for story_plan, count in zip(story_plans, counts, strict=True):
                ctx.add_story_context(
                    StoryContext.from_plan(story_plan, expected_word_count=count)
                    .set_language(ctx.language)
                    .set_rag(ctx.rag)
                    .set_writing_constraint(
                        merge_writing_constraints(ctx.writing_constraint, story_plan.writing_constraint)
                    )
                )
            logger.info(f"Planned {len(ctx.story_context)} story(s) for chapter '{ctx.title}'")
        await self.draft_story_spans(ctx, send_to, **kwargs)
        return True

    async def compose_stories_phase(
        self,
        ctx: ChapterContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Broadcast the bible and compose every story in prefix order.

        Returns:
            bool: True when every story composed; False on any failure.
        """
        ctx.broadcast_settings_bible()
        total = len(ctx.story_context)
        for i, story_ctx in enumerate(ctx.iter_prefixed_contexts(), start=1):
            logger.info(f"Composing story {i}/{total} '{story_ctx.title}'")
            if await self.compose_story(story_ctx, send_to, **kwargs) is None:
                logger.error(f"Story '{story_ctx.title}' failed; aborting chapter '{ctx.title}'")
                return False
        return True

    async def generate_chapter(
        self,
        ctx: ChapterContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Chapter | None:
        """Generate the chapter by composing its stories.

        Runs the staged phases in order: story planning, story composition,
        and chapter assembly. Returns the materialized chapter or None when
        any phase fails.
        """
        logger.debug(f"Generating chapter '{ctx.title}'")
        if not await self.plan_stories_phase(ctx, send_to, **kwargs):
            return None
        if not await self.compose_stories_phase(ctx, send_to, **kwargs):
            return None
        chapter = Chapter.from_context(ctx)
        logger.info(
            f"Chapter '{chapter.title}' composed ({len(chapter.story)} story(s),  word count satisfaction: {chapter.satisfy_ratio()}"
        )
        return chapter

    async def compose_chapter(
        self,
        ctx: ChapterContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Chapter | None:
        """Compose a chapter end to end: before, generate, after, then post-process; returns None when generation fails."""
        ctx = await self.before_compose_chapter(ctx, **kwargs)
        chapter = await self.generate_chapter(ctx, send_to, **kwargs)
        ctx = await self.after_compose_chapter(ctx, **kwargs)

        if chapter is None:
            return None
        return await self.post_process_chapter(ctx, chapter, **kwargs)

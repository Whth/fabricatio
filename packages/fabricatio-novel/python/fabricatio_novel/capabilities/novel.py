"""Novel composition capabilities: planning chapters and composing novels."""

from abc import ABC
from typing import Callable, Sequence, Unpack

from fabricatio_character.models.character import CharacterCard, CharacterCardBoundaries
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_core.utils import ok

from fabricatio_novel.capabilities.chapter import ChapterCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.base import (
    CharacterSpan,
    CharacterSpans,
    derive_child_spans,
    merge_writing_constraints,
)
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.models.plan import ChapterPlan, ChapterPlans, NovelPlan


class NovelCompose(ChapterCompose, ABC):
    """This class contains the capabilities for the novel."""

    async def before_compose_novel(
        self,
        ctx: NovelContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> NovelContext:
        """Identity hook invoked before composing a novel; may mutate the context."""
        return ctx

    async def after_compose_novel(
        self,
        ctx: NovelContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> NovelContext:
        """Identity hook invoked after generating a novel; may mutate the context."""
        return ctx

    async def post_process_novel(self, ctx: NovelContext, novel: Novel, **kwargs: Unpack[LLMKwargs]) -> Novel:
        """Identity hook invoked on the composed novel; may transform and return the novel."""
        return novel

    async def plan_chapters(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[ChapterPlan] | None:
        """Propose chapter plans for the novel via the LLM.

        Renders the chapter plan template from the novel outline and context
        and proposes a ChapterPlans batch, returning the root list of plans
        or None on failure.
        """
        logger.debug("Planning chapters from outline")
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.chapter_plan_template,
            {
                "outline": ctx.outline,
                "language": ctx.language,
                "title": ctx.title,
                "description": ctx.description,
                "expected_word_count": ctx.expected_word_count,
                "writing_style": ctx.writing_style,
                "writing_constraint": ctx.writing_constraint,
                "characters": ctx.dump_characters(),
            },
        )
        plans = await self.propose(ChapterPlans, requirement, send_to=send_to, **kwargs)
        return plans.root if plans is not None else None

    async def propose_novel_metadata(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Propose the novel metadata from the outline and adopt it onto the context.

        Returns:
            bool: True when the plan was proposed and adopted; False on failure.
        """
        logger.debug("Proposing novel metadata from outline")
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.novel_metadata_requirement_template,
            {"outline": ctx.outline, "language": ctx.language, "constraint": ctx.writing_constraint},
        )
        plan = await self.propose(NovelPlan, requirement, send_to, **kwargs)
        if plan is None:
            logger.error("Novel metadata proposal failed; aborting novel generation")
            return False
        ctx.set_novel_plan(plan).update_from(plan)
        logger.info(f"Novel plan proposed: '{plan.title}' ({plan.expected_word_count} words)")
        return True

    async def prepare_character_span(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> None:
        """Propose the novel roster as one CharacterSpan per character in a single batch.

        Skipped silently when the settings bible has no character roster so
        tests and runs without a character cast pass through unchanged.
        """
        bible = ctx.series_bible
        if bible is None or not bible.characters:
            return
        spans = ok(
            await self.propose(
                CharacterSpans,
                TEMPLATE_MANAGER.render_template(
                    novel_config.novel_character_span_template,
                    {"bible": bible.as_prompt(), "desc": ctx.description, "title": ctx.title},
                ),
                send_to=send_to,
                **kwargs,
            )
        )
        ctx.set_charactor_spans(spans.root)
        logger.info(f"Proposed {len(ctx.charactor_span)} novel character span(s)")

    async def draft_chapter_spans(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> None:
        """Draft the N-1 chapter-boundary cards per character in a single LLM batch.

        The novel roster already fixes the endpoints: chapter 1 starts at
        the roster start card and the last chapter ends at the roster end
        card. Only the boundaries between consecutive chapters are proposed;
        the spans are stitched in code so the chain is continuous by
        construction. Skipped silently when the novel has no roster spans or
        no chapters, so tests and runs without a roster pass through
        unchanged. A single chapter inherits the roster spans directly
        without any LLM call.
        """
        if not ctx.charactor_span or not ctx.chapter_context:
            return
        if len(ctx.chapter_context) == 1:
            ctx.chapter_context[0].set_charactor_spans(ctx.charactor_span)
            logger.debug("Single chapter inherits the novel roster spans")
            return
        logger.debug(f"Drafting {len(ctx.chapter_context) - 1} chapter boundary card(s) per character")
        proposed = ok(
            await self.propose(
                CharacterCardBoundaries,
                TEMPLATE_MANAGER.render_template(
                    novel_config.chapter_character_span_template,
                    {
                        "novel_title": ctx.title,
                        "novel_description": ctx.description,
                        "language": ctx.language,
                        "roster_spans": ctx.dump_characters(),
                        "chapters": [{"title": c.title, "description": c.description} for c in ctx.chapter_context],
                    },
                ),
                send_to=send_to,
                **kwargs,
            )
        )
        self._stitch_boundaries(
            ctx.charactor_span,
            ctx.chapter_context,
            lambda chapter_ctx: chapter_ctx.charactor_span,
            proposed.root,
            len(ctx.chapter_context) - 1,
            "chapter",
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

    async def plan_chapters_phase(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Plan chapters when none are scheduled, materialize their contexts, and draft spans.

        Returns:
            bool: True when the chapters are planned; False on planning failure.
        """
        if not ctx.chapter_context:
            chapter_plans = await self.plan_chapters(ctx, send_to, **kwargs)
            if chapter_plans is None:
                logger.error("Chapter planning failed; aborting novel generation")
                return False
            counts = ctx.allocate([p.weight for p in chapter_plans]) if chapter_plans else []
            for chapter_plan, count in zip(chapter_plans, counts, strict=True):
                ctx.add_chapter_context(
                    ChapterContext.from_plan(chapter_plan, expected_word_count=count)
                    .set_language(ctx.language)
                    .set_rag(ctx.rag)
                    .set_writing_constraint(
                        merge_writing_constraints(ctx.writing_constraint, chapter_plan.writing_constraint)
                    )
                )
            logger.info(f"Planned {len(ctx.chapter_context)} chapter(s)")
        await self.draft_chapter_spans(ctx, send_to, **kwargs)
        return True

    async def compose_chapters_phase(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Broadcast the bible and compose every chapter in prefix order.

        Returns:
            bool: True when every chapter composed; False on any failure.
        """
        ctx.broadcast_settings_bible()
        total = len(ctx.chapter_context)
        for i, chapter_ctx in enumerate(ctx.iter_prefixed_contexts(), start=1):
            logger.info(f"Composing chapter {i}/{total} '{chapter_ctx.title}'")
            if await self.compose_chapter(chapter_ctx, send_to, **kwargs) is None:
                logger.error(f"Chapter '{chapter_ctx.title}' failed; aborting novel generation")
                return False
        return True

    def assemble_novel(self, ctx: NovelContext) -> Novel:
        """Materialize the composed context tree as a Novel."""
        novel = Novel.from_context(ctx)
        logger.info(
            f"Novel '{novel.title}' composed ({len(novel.chapter)} chapter(s), word count satisfaction: {novel.satisfy_ratio()}"
        )
        return novel

    async def generate_novel(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Novel | None:
        """Generate the novel by composing its chapters.

        Runs the staged phases in order: metadata proposal, roster character
        span creation, chapter planning with span drafting, chapter
        composition, and novel assembly. Returns the materialized novel or
        None when any phase fails.
        """
        logger.info(f"Generating novel from outline ({len(ctx.outline)} characters)")
        if not await self.propose_novel_metadata(ctx, send_to, **kwargs):
            return None
        await self.prepare_character_span(ctx, send_to, **kwargs)
        if not await self.plan_chapters_phase(ctx, send_to, **kwargs):
            return None
        if not await self.compose_chapters_phase(ctx, send_to, **kwargs):
            return None
        return self.assemble_novel(ctx)

    async def compose_novel(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Novel | None:
        """Compose a novel end to end: before, generate, after, then post-process; returns None when generation fails."""
        ctx = await self.before_compose_novel(ctx, **kwargs)
        novel = await self.generate_novel(ctx, send_to, **kwargs)
        ctx = await self.after_compose_novel(ctx, **kwargs)

        if novel is None:
            return None
        return await self.post_process_novel(ctx, novel, **kwargs)

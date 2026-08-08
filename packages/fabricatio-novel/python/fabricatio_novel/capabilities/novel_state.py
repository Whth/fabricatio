"""Character state consistency integration for novel composition.

Provides optional physical/circumstantial state tracking for characters during
novel generation. After each chapter is generated, the raw prose is audited
through the :meth:`NovelComposeState.after_chapter_gen` hook: per-character
state sequences are extracted (paragraph-anchored), local adjacency and global
reachability are judged in the same batched call, and violations trigger ONE
regeneration pass. A Character State Board is injected into the chapter prompt
so the writer keeps every character consistent. The capability itself stays
stateless — all per-run state lives in the caller-owned
:class:`StateChapterContext` channel, whose state domain (histories,
violations, board/baseline rendering) is sealed in :class:`StateLedger`.

Usage::

    from fabricatio_novel.capabilities.novel_state import NovelComposeState

    class MyComposer(NovelComposeState):
        pass
"""

from typing import List, Optional, Self, Unpack

from fabricatio_character.models.character import CharacterCard
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import SMOL
from fabricatio_core.utils import no_default, ok
from pydantic import Field

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.capabilities.state_ledger import StateLedger
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.chapter_context import ChapterContext
from fabricatio_novel.models.chapter_state import ChapterStateRecord
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.utils import number_paragraphs


class StateChapterContext(ChapterContext):
    """Chapter context extended with character state consistency tracking.

    The caller passes it as ``context`` to ``create_chapters``; the state
    domain (histories, violations, board/baseline rendering) is sealed in
    :class:`StateLedger` and mutated through the thin chainable delegates
    below, so the caller observes the evolution without any instance state on
    the capability.
    """

    state_ledger: StateLedger = Field(default_factory=StateLedger)
    """Sealed state-domain store: histories + violations + board/baseline renders."""

    def extend_state_violations(self, violations: List[str]) -> Self:
        """Append violations to the ledger's durable store and return self (chainable)."""
        self.state_ledger.extend_violations(violations)
        return self

    def record_chapter_states(self, record: ChapterStateRecord) -> Self:
        """Commit one chapter's extraction record to the ledger and return self (chainable)."""
        self.state_ledger.record(record, self.chapter_index(), self.characters)
        return self

    def state_board_context(self) -> str:
        """Render the Character State Board as concise prompt injection."""
        return self.state_ledger.board_context(self.characters)

    def _previous_states_context(self) -> str:
        """Render per-character previous chapter-end states (reachability baseline)."""
        return self.state_ledger.previous_states_context(self.characters)


class NovelComposeState(NovelCompose):
    """Mixin that adds character state consistency to novel composition.

    The caller-owned :class:`StateChapterContext` carries the
    :class:`StateLedger` (histories + violations) through the base
    ``create_chapters`` loop; the hooks (:meth:`extra_chapter_prompt_vars` /
    :meth:`after_chapter_gen`) inject the state board and run the audit gate.
    The capability itself stays stateless between runs.
    """

    # ── Public API ──

    async def build_chapter_context(self, characters: List[CharacterCard]) -> StateChapterContext:
        """Build the caller-owned chapter context for a run (no seeding needed).

        Overridable seam — combined mixins override it to return their own
        context subclass carrying extra fields.
        """
        return StateChapterContext()

    async def compose_novel(
        self,
        outline: str,
        language: str | None = None,
        chapter_guidance: str | None = None,
        **kwargs: Unpack[ValidateKwargs[Novel]],
    ) -> "Novel | None":
        """Novel composition pipeline with character state consistency."""
        okwargs = no_default(kwargs)

        result = await super().generate_draft_and_characters(outline, language, **okwargs)
        if not result:
            return None
        draft, characters = result

        context = await self.build_chapter_context(characters)

        plans = await super().generate_plans(draft, characters, **okwargs)
        if not plans:
            return None

        chapters = await self.create_chapters(draft, plans, characters, chapter_guidance, context=context, **okwargs)
        if not chapters:
            return None

        return self.assemble_novel(draft, plans, chapters, characters)

    # ── Chapter hooks ──

    def extra_chapter_prompt_vars(self, ctx: ChapterContext) -> None:
        """Contribute the Character State Board to the chapter prompt template vars.

        Cooperative: delegates to the super() chain first, then adds its own
        key to ``ctx.chapter_prompt_vars`` — sibling mixins each add their own
        keys, so diamonds compose without shadowing.
        """
        super().extra_chapter_prompt_vars(ctx)
        if isinstance(ctx, StateChapterContext):
            ctx.add_prompt_vars({"character_state_board": ctx.state_board_context()})

    async def after_chapter_gen(self, ctx: ChapterContext) -> None:
        """Audit the raw chapter: extract states, judge plausibility, regenerate once on violations."""
        if not isinstance(ctx, StateChapterContext):
            return
        raw = ctx.pending_chapter()
        if raw is None:
            return

        record = await self._extract_state_record(ctx, raw)
        if record is None:
            message = f"State extraction failed for chapter {ctx.chapter_index()} — chapter end states unknown"
            ctx.extend_state_violations([message])
            logger.warn(message)
            return

        if record.violations:
            ctx.extend_state_violations(record.violations)
            logger.info(
                f"Chapter {ctx.chapter_index() + 1}: {len(record.violations)} violation(s) found — regenerating once"
            )
            rendered = await self.prepare_chapter_prompt(ctx)
            rewrite = self._build_rewrite_request(raw, record.violations)
            new_raw = ok(await self.aask(f"{rendered}\n\n{rewrite}"))
            ctx.set_pending_chapter(ctx.chapter_index(), new_raw)

            final = await self._extract_state_record(ctx, new_raw)
            if final is None:
                message = (
                    f"State re-extraction failed for chapter {ctx.chapter_index()} "
                    "after regeneration — chapter end states unknown"
                )
                ctx.extend_state_violations([message])
                logger.warn(message)
                return
            ctx.record_chapter_states(final)
            logger.info(
                f"Chapter {ctx.chapter_index() + 1} regenerated once; "
                f"{len(final.violations)} residual state violation(s) accepted"
            )
            return

        ctx.record_chapter_states(record)
        logger.debug(f"Chapter {ctx.chapter_index() + 1}: tracked {len(record.characters)} character(s), 0 violations")

    # ── Helpers ──

    async def _extract_state_record(self, ctx: StateChapterContext, raw: str) -> Optional[ChapterStateRecord]:
        """Run the batched state extraction + plausibility judgment over raw prose."""
        if ctx.characters is None or ctx.draft is None:
            logger.debug(f"State extraction skipped for chapter {ctx.chapter_index() + 1}: channel inputs unset")
            return None
        prompt = TEMPLATE_MANAGER.render_template(
            novel_config.chapter_state_extraction_template,
            {
                "language": ctx.draft.language,
                "characters": [card.name for card in ctx.characters],
                "previous_states": ctx._previous_states_context(),
                "chapter_content": number_paragraphs(raw),
            },
        )
        return await self.propose(ChapterStateRecord, prompt, send_to=SMOL)

    def _build_rewrite_request(self, raw: str, violations: List[str]) -> str:
        """Render the REWRITE REQUEST appendix for the regeneration prompt."""
        return TEMPLATE_MANAGER.render_template(
            novel_config.chapter_rewrite_request_template,
            {"violations": violations, "draft": raw},
        )

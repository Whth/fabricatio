"""Character state consistency integration for novel composition.

Provides optional physical/circumstantial state tracking for characters during
novel generation. After each chapter is generated, the raw prose is audited
through the :meth:`NovelComposeState.after_chapter_gen` hook: per-character
state sequences are extracted (paragraph-anchored), local adjacency and global
reachability are judged in the same batched call, and violations trigger ONE
regeneration pass. A Character State Board is injected into the chapter prompt
so the writer keeps every character consistent. The capability itself stays
stateless — all per-run state lives in the caller-owned
:class:`StateChapterContext` channel.

Usage::

    from fabricatio_novel.capabilities.novel_state import NovelComposeState

    class MyComposer(NovelComposeState):
        pass
"""

import re
from typing import Any, Dict, List, Optional, Self, Tuple, Unpack

from fabricatio_character.models.character import CharacterCard
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import SMOL
from fabricatio_core.utils import no_default, ok
from pydantic import Field

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.chapter_context import ChapterContext
from fabricatio_novel.models.chapter_state import ChapterStateRecord
from fabricatio_novel.models.novel import Novel


class StateChapterContext(ChapterContext):
    """Chapter context extended with character state consistency tracking.

    The caller passes it as ``context`` to ``create_chapters``; the state
    hooks mutate the fields in place, so the caller observes the evolution
    without any instance state on the capability.
    """

    character_state_histories: Dict[str, List[Tuple[int, str]]] = Field(default_factory=dict)
    """Global layer: character name -> [(chapter_index, end state), ...] in chapter order."""

    character_in_chapter_states: Dict[str, List[str]] = Field(default_factory=dict)
    """Local layer: character name -> this chapter's change-point state sequence."""

    state_violations: List[str] = Field(default_factory=list)
    """Durable log of human-readable violations across all chapters."""

    def extend_state_violations(self, violations: List[str]) -> Self:
        """Append violations to the durable log and return self (chainable)."""
        self.state_violations.extend(violations)
        return self

    def record_chapter_states(self, record: ChapterStateRecord) -> Self:
        """Commit one chapter's extraction record to the channel and return self (chainable).

        Appends each character's end state to the global history (tagged with
        the current chapter index), replaces the local change-point sequence,
        carries forward the previous end state for characters absent from the
        record (re-appended under the current chapter index; skipped when they
        have no history entry), removes absent characters from the local
        layer, and logs the record's residual violations.
        """
        current = self.chapter_index()
        recorded = set()
        for cs in record.characters:
            recorded.add(cs.character)
            history = self.character_state_histories.get(cs.character, [])
            self.character_state_histories[cs.character] = [*history, (current, cs.chapter_end_state)]
            if cs.states:
                self.character_in_chapter_states[cs.character] = list(cs.states)
            else:
                self.character_in_chapter_states.pop(cs.character, None)
        known = set(self.character_state_histories)
        if self.characters:
            known |= {card.name for card in self.characters}
        for name in known - recorded:
            history = self.character_state_histories.get(name, [])
            if history:
                self.character_state_histories[name] = [*history, (current, history[-1][1])]
            self.character_in_chapter_states.pop(name, None)
        self.state_violations.extend(record.violations)
        return self


class NovelComposeState(NovelCompose):
    """Mixin that adds character state consistency to novel composition.

    The caller-owned :class:`StateChapterContext` carries the histories and
    violations through the base ``create_chapters`` loop; the hooks
    (:meth:`extra_chapter_prompt_vars` / :meth:`after_chapter_gen`) inject the
    state board and run the audit gate. The capability itself stays stateless
    between runs.
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
            ctx.add_prompt_vars({"character_state_board": state_board_context(ctx)})

    async def after_chapter_gen(self, ctx: ChapterContext) -> None:
        """Audit the raw chapter: extract states, judge plausibility, regenerate once on violations."""
        if not isinstance(ctx, StateChapterContext):
            return
        raw = ctx.pending_chapter()
        if raw is None:
            return

        record = await self._extract_state_record(ctx, raw)
        if record is None:
            ctx.extend_state_violations(
                [f"State extraction failed for chapter {ctx.chapter_index()} — chapter end states unknown"]
            )
            return

        if record.violations:
            ctx.extend_state_violations(record.violations)
            rendered = await self.prepare_chapter_prompt(ctx)
            rewrite = self._build_rewrite_request(raw, record.violations)
            new_raw = ok(await self.aask(f"{rendered}\n\n{rewrite}"))
            ctx.set_pending_chapter(ctx.chapter_index(), new_raw)

            final = await self._extract_state_record(ctx, new_raw)
            if final is None:
                ctx.extend_state_violations(
                    [
                        f"State re-extraction failed for chapter {ctx.chapter_index()} "
                        "after regeneration — chapter end states unknown"
                    ]
                )
                return
            ctx.record_chapter_states(final)
            logger.info(
                f"Chapter {ctx.chapter_index() + 1} regenerated once; "
                f"{len(final.violations)} residual state violation(s) accepted"
            )
            return

        ctx.record_chapter_states(record)

    # ── Helpers ──

    async def _extract_state_record(self, ctx: StateChapterContext, raw: str) -> Optional[ChapterStateRecord]:
        """Run the batched state extraction + plausibility judgment over raw prose."""
        if ctx.characters is None or ctx.draft is None:
            return None
        prompt = TEMPLATE_MANAGER.render_template(
            novel_config.chapter_state_extraction_template,
            {
                "language": ctx.draft.language,
                "characters": [card.name for card in ctx.characters],
                "previous_states": self._previous_states_context(ctx),
                "chapter_content": number_paragraphs(raw),
            },
        )
        return await self.propose(ChapterStateRecord, prompt, send_to=SMOL)

    def _previous_states_context(self, ctx: StateChapterContext) -> str:
        """Render per-character previous chapter-end states (reachability baseline)."""
        states: List[Dict[str, Any]] = []
        if ctx.characters is not None:
            for card in ctx.characters:
                history = ctx.character_state_histories.get(card.name, [])
                if history:
                    idx, state = history[-1]
                    states.append({"name": card.name, "state": state, "chapter": idx, "has_chapter": True})
                else:
                    states.append({"name": card.name, "state": None, "chapter": None, "has_chapter": False})
        return TEMPLATE_MANAGER.render_template(
            novel_config.chapter_previous_states_template,
            {"states": states},
        ).strip()

    def _build_rewrite_request(self, raw: str, violations: List[str]) -> str:
        """Render the REWRITE REQUEST appendix for the regeneration prompt."""
        return TEMPLATE_MANAGER.render_template(
            novel_config.chapter_rewrite_request_template,
            {"violations": violations, "draft": raw},
        )


def state_board_context(ctx: StateChapterContext) -> str:
    """Render the Character State Board as concise prompt injection."""
    names = set(ctx.character_state_histories)
    if ctx.characters:
        names |= {card.name for card in ctx.characters}
    states: List[Dict[str, Any]] = []
    for name in sorted(names):
        history = ctx.character_state_histories.get(name, [])
        if history:
            idx, state = history[-1]
            states.append({"name": name, "state": state, "chapter": idx, "has_chapter": True})
        else:
            states.append({"name": name, "state": None, "chapter": None, "has_chapter": False})
    warnings: List[str] = []
    if ctx.state_violations:
        seen = set()
        for violation in ctx.state_violations:
            if violation not in seen:
                seen.add(violation)
                warnings.append(violation)
    return TEMPLATE_MANAGER.render_template(
        novel_config.character_state_board_template,
        {"states": states, "warnings": warnings},
    ).strip()


def number_paragraphs(raw: str) -> str:
    """Number the raw chapter's blank-line-separated paragraphs (0-based ``P0:``, ``P1:``, ...)."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    return "\n\n".join(f"P{i}: {p}" for i, p in enumerate(paragraphs))

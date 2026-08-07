"""Mental state integration for novel composition.

Provides optional psychological state tracking for characters during novel
generation. Characters are seeded with mental states from their CharacterCard,
and states evolve after each chapter via LLM event analysis.

Usage::

    from fabricatio_novel.capabilities.novel_mental import NovelComposeMental

    class MyComposer(NovelComposeMental):
        pass
"""

from typing import TYPE_CHECKING, Any, Dict, List, Unpack

from fabricatio_character.capabilities.mental import UseMind
from fabricatio_character.models.character import CharacterCard
from fabricatio_character.models.mental import MentalState
from fabricatio_core import logger
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.utils import no_default
from pydantic import Field

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.models.chapter_context import ChapterContext
from fabricatio_novel.models.novel import Novel

if TYPE_CHECKING:
    from fabricatio_novel.models.scripting import ChapterSummary


class MentalChapterContext(ChapterContext):
    """Chapter context extended with per-run character mental states.

    The caller (``compose_novel`` / action ``_execute``) seeds it and passes it
    as ``context`` to :meth:`NovelCompose.create_chapters`; the mental hooks
    mutate ``character_states`` in place, so the caller observes the evolution
    without any instance state on the capability.
    """

    character_states: Dict[str, MentalState] = Field(default_factory=dict)
    """Current mental state per character name, evolved after each chapter."""


class NovelComposeMental(NovelCompose, UseMind):
    """Mixin that adds psychological state tracking to novel composition.

    Seeding happens in :meth:`compose_novel`, the caller-owned
    :class:`MentalChapterContext` carries the states through the base
    ``create_chapters`` loop, and the hooks (:meth:`extra_chapter_prompt_vars` /
    :meth:`after_chapter_summarize`) inject and evolve them. The capability
    itself stays stateless between runs.
    """

    # ── Public API ──

    async def seed_mental_states(self, characters: List[CharacterCard]) -> Dict[str, "MentalState"]:
        """Seed mental states for a list of characters.

        Standalone entry point — does not require the novel pipeline.
        """
        states: Dict[str, MentalState] = {}
        for card in characters:
            states[card.name] = await self.seed_from(card.name, card.want, card.flaw)
        logger.info(f"Seeded mental states for {len(states)} character(s)")
        return states

    def character_system_prompt(self, states: Dict[str, MentalState], name: str) -> str:
        """Get the system prompt for a character based on their current mental state."""
        state = states.get(name)
        return self.as_prompt(state) if state else ""

    # ── Pipeline overrides ──

    async def build_chapter_context(self, characters: List[CharacterCard]) -> MentalChapterContext:
        """Build the caller-owned chapter context for a run (seeds mental states).

        Overridable seam — combined mixins (e.g. ``NovelComposeMentalRAG``)
        override it to return their own context subclass carrying extra fields.
        """
        return MentalChapterContext(character_states=await self.seed_mental_states(characters))

    async def compose_novel(
        self,
        outline: str,
        language: str | None = None,
        chapter_guidance: str | None = None,
        **kwargs: Unpack[ValidateKwargs[Novel]],
    ) -> "Novel | None":
        """Novel composition pipeline with mental state integration."""
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

    def extra_chapter_prompt_vars(self, ctx: ChapterContext) -> Dict[str, Any]:
        """Contribute current mental states to the chapter prompt template vars.

        Cooperative: merges the super() chain's contribution first so sibling
        mixins (e.g. character state boards) are not shadowed in diamonds.
        """
        merged = super().extra_chapter_prompt_vars(ctx)
        if isinstance(ctx, MentalChapterContext) and ctx.character_states:
            merged["character_mental_states"] = mental_states_context(ctx.character_states)
        return merged

    async def after_chapter_summarize(self, ctx: ChapterContext) -> None:
        """Evolve character mental states after each chapter summary."""
        if not isinstance(ctx, MentalChapterContext):
            return
        states = ctx.character_states
        summary = ctx.current_summary()
        if not states or summary is None:
            return
        char_events = build_character_events(summary, states)
        for name, state in list(states.items()):
            event = char_events.get(name, "")
            if event:
                impact = await self.upon_event(event, state)
                states[name] = self.after_impact(impact, state)
        logger.debug(f"Evolved mental states for {len(states)} character(s)")


def build_character_events(summary: "ChapterSummary", states: Dict[str, "MentalState"]) -> Dict[str, str]:
    """Build per-character event strings from chapter summary."""
    events: Dict[str, str] = {}
    for name in states:
        matched = [e for e in summary.key_events if name.lower() in e.lower()]
        if matched:
            events[name] = "; ".join(matched)
    return events


def mental_states_context(states: Dict[str, "MentalState"]) -> str:
    """Render character mental states as concise prompt injection."""
    lines: List[str] = []
    for name, state in states.items():
        mood = state.emotion.emotion  # StrEnum → already a str
        tension = f"tension={state.emotion.intensity:.0f}" if state.emotion.intensity else ""
        parts = [f"{name}: mood={mood}"]
        if tension:
            parts.append(tension)
        if state.emotion.active_distortion:
            parts.append(f"distortion={state.emotion.active_distortion}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)

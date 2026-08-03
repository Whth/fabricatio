"""Mental state integration for novel composition.

Provides optional psychological state tracking for characters during novel
generation. Characters are seeded with mental states from their CharacterCard,
and states evolve after each chapter via LLM event analysis.

Usage::

    from fabricatio_novel.capabilities.novel_mental import MentalComposeMixin

    class MyComposer(MentalComposeMixin):
        pass
"""

from typing import TYPE_CHECKING, Awaitable, Callable, Dict, List, Optional, Unpack

from fabricatio_character.capabilities.mental import UseMind
from fabricatio_character.models.character import CharacterCard
from fabricatio_character.models.mental import MentalState
from fabricatio_core import logger
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import TASK
from fabricatio_core.utils import no_default

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.models.novel import Novel

if TYPE_CHECKING:
    from fabricatio_novel.models.draft import NovelDraft
    from fabricatio_novel.models.plan import ChapterPlan
    from fabricatio_novel.models.scripting import ChapterSummary


class NovelComposeMental(NovelCompose, UseMind):
    """Mixin that adds psychological state tracking to novel composition.

    Overrides compose_novel and create_chapters to seed, inject, and evolve
    character mental states. Reuses all base class methods via super().
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
        """Get the system prompt for a character based on their current mental state.

        Returns empty string if character not found.
        """
        state = states.get(name)
        return self.as_prompt(state) if state else ""

    # ── Pipeline overrides ──

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

        character_states = await self.seed_mental_states(characters)

        plans = await super().generate_plans(draft, characters, **okwargs)
        if not plans:
            return None

        chapters = await self.create_chapters(
            draft, plans, characters, chapter_guidance, character_states=character_states, **okwargs
        )
        if not chapters:
            return None

        return self.assemble_novel(draft, plans, chapters, characters)

    async def create_chapters(
        self,
        draft: "NovelDraft",
        chapter_plans: "List[ChapterPlan]",
        characters: "List[CharacterCard]",
        guidance: Optional[str] = None,
        send_to: Optional[str] = TASK,
        prompt_ctx_extend: Optional[Callable[[dict], dict]] = None,
        after_summarize: Optional[Callable[["ChapterSummary"], Awaitable[None]]] = None,
        character_states: Optional[Dict[str, MentalState]] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> List[str]:
        """Generate chapters with mental state injection and evolution.

        Wraps base class create_chapters: injects mental states into prompt
        context before each chapter, evolves states after each chapter summary,
        and threads the last paragraph of the prior chapter
        (``previous_chapter_tail``) alongside the rolling summary so the
        next chapter opens off the prior chapter's closing beat.
        """
        if not character_states:
            return await super().create_chapters(
                draft,
                chapter_plans,
                characters,
                guidance=guidance,
                send_to=send_to,
                prompt_ctx_extend=prompt_ctx_extend,
                after_summarize=after_summarize,
                **kwargs,
            )

        async def after_summarize_hook(summary: "ChapterSummary") -> None:
            """Evolve mental states after each chapter's summary is generated."""
            char_events = build_character_events(summary, character_states)
            for name, state in list(character_states.items()):
                event = char_events.get(name, "")
                if event:
                    impact = await self.upon_event(event, state)
                    character_states[name] = self.after_impact(impact, state)
            logger.debug(f"Evolved mental states for {len(character_states)} character(s)")

        def prompt_ctx_extend_inner(prompt_ctx: dict) -> dict:
            """Inject mental states into prompt context before rendering."""
            prompt_ctx["character_mental_states"] = mental_states_context(character_states)
            return prompt_ctx

        return await super().create_chapters(
            draft,
            chapter_plans,
            characters,
            guidance=guidance,
            send_to=send_to,
            prompt_ctx_extend=prompt_ctx_extend_inner,
            after_summarize=after_summarize_hook,
            **kwargs,
        )


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

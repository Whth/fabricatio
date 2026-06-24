"""Mental state integration for novel composition.

Provides optional psychological state tracking for characters during novel
generation. Characters are seeded with mental states from their CharacterCard,
and states evolve after each chapter via LLM event analysis.

Usage::

    from fabricatio_novel.capabilities.novel_mental import MentalComposeMixin

    class MyComposer(MentalComposeMixin):
        pass
"""

from typing import TYPE_CHECKING, Dict, List, Unpack

from fabricatio_character.capabilities.mental import UseMind
from fabricatio_character.models.character import CharacterCard
from fabricatio_character.models.mental import MentalState
from fabricatio_character.utils import dump_card
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.utils import ok, override_kwargs

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.config import novel_config
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
        okwargs = override_kwargs(kwargs, default=None)

        result = await super().generate_draft_and_characters(outline, language, **okwargs)
        if not result:
            return None
        draft, characters = result

        character_states = await self.seed_mental_states(characters)

        plans = await super().generate_plans(draft, characters, **okwargs)
        if not plans:
            return None

        chapters = await self.create_chapters(draft, plans, characters, chapter_guidance, character_states, **okwargs)
        if not chapters:
            return None

        return self.assemble_novel(draft, plans, chapters, characters)

    async def create_chapters(
        self,
        draft: "NovelDraft",
        chapter_plans: "List[ChapterPlan]",
        characters: "List[CharacterCard]",
        guidance: str | None = None,
        character_states: Dict[str, "MentalState"] | None = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> List[str]:
        """Generate chapters with mental state injection and evolution.

        Wraps base class create_chapters: injects mental states into prompt
        context before each chapter, evolves states after each chapter summary.
        """
        if not character_states:
            return await super().create_chapters(draft, chapter_plans, characters, guidance, **kwargs)

        character_prompt = dump_card(*characters)
        chapter_contents: List[str] = []
        previous_summary: ChapterSummary | None = None

        for i, cp in enumerate(chapter_plans):
            logger.debug(f"Chapter {i + 1}/{len(chapter_plans)}: {cp.formatted_chapter_title}")

            # Build prompt with mental states injected
            prompt_ctx = {
                "script": cp.script.as_prompt(),
                "characters": character_prompt,
                "character_mental_states": mental_states_context(character_states),
                "language": draft.language,
                "guidance": guidance,
                "expected_word_count": cp.expected_word_count,
                "chapter_title": cp.formatted_chapter_title,
                "novel_title": draft.title,
                "novel_synopsis": draft.synopsis,
                "all_chapters_titles": draft.all_chapters_titles,
                "previous_summary": previous_summary.as_prompt() if previous_summary else None,
            }
            rendered = TEMPLATE_MANAGER.render_template(novel_config.chapter_requirement_template, [prompt_ctx])

            # Generate chapter
            raw_chapter = ok(await self.aask(rendered, **kwargs))
            if not raw_chapter:
                logger.warn(f"Failed to generate {cp.formatted_chapter_title}")
                chapter_contents.append("")
                continue

            raw_text = raw_chapter[0]
            chapter_contents.append(raw_text)
            logger.info(f"Chapter {i + 1}/{len(chapter_plans)} generated ({len(raw_text)} chars)")

            # Summarize (reuse base)
            previous_summary = await self.summarize_chapter(
                cp.formatted_chapter_title, raw_text, draft.language, previous_summary, **kwargs
            )

            # Evolve mental states
            if previous_summary:
                char_events = build_character_events(previous_summary, character_states)
                for name, state in list(character_states.items()):
                    event = char_events.get(name, "")
                    if event:
                        impact = await self.upon_event(event, state)
                        character_states[name] = self.after_impact(impact, state)
                logger.debug(f"Chapter {i + 1}: evolved mental states for {len(character_states)} character(s)")

        logger.info(f"Generated {len(chapter_contents)} chapter(s) with mental states")
        return chapter_contents


# ── Pure helpers (no self — stateless) ──


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

"""Mental state-aware novel generation actions.

These actions use NovelComposeMental to inject psychological state tracking
into the novel generation pipeline. Characters are seeded with mental states
from their CharacterCard, and states evolve after each chapter.
"""

from typing import TYPE_CHECKING, Any, ClassVar, List, Optional

from fabricatio_character.models.character import CharacterCard
from fabricatio_core import Action, logger
from fabricatio_core.utils import ok

from fabricatio_novel.capabilities.novel_mental import NovelComposeMental
from fabricatio_novel.capabilities.novel_mental_rag import NovelComposeMentalRAG
from fabricatio_novel.models.draft import NovelDraft
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.scripting import Script

if TYPE_CHECKING:
    from fabricatio_novel.models.novel_rag import WritingStyleFetchConfig


class GenerateNovelMental(NovelComposeMental, Action):
    """One-step novel generation with mental state tracking.

    Calls compose_novel which seeds mental states, generates chapters with
    state injection, and evolves states after each chapter.
    """

    novel_outline: Optional[str] = None
    """The prompt used to generate the novel."""

    novel_language: Optional[str] = None
    """The language of the novel."""

    chapter_guidance: Optional[str] = None
    """Guidance for writing chapter."""

    output_key: str = "novel"
    """Key under which the generated novel will be stored in context."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt) -> Novel | None:
        return await self.compose_novel(ok(self.novel_outline), self.novel_language, self.chapter_guidance)


class GenerateChaptersFromScriptsWithMental(NovelComposeMental, Action):
    """Generate chapters with mental state injection and evolution.

    Seeds mental states from character cards, generates chapters with
    psychological context injected into prompts, and evolves states
    after each chapter summary.
    """

    novel_draft: Optional[NovelDraft] = None
    """The novel draft (for language, metadata)."""

    novel_scripts: Optional[List[Script]] = None
    """The list of chapter scripts to expand into full text."""

    novel_characters: Optional[List[CharacterCard]] = None
    """The list of characters to provide context and seed mental states."""

    chapter_guidance: Optional[str] = None
    """Guidance for writing chapter."""

    output_key: str = "novel_chapter_contents"
    """Key under which the generated chapter contents will be stored in context."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt) -> List[str] | List[str | None] | None:
        draft = ok(self.novel_draft)
        scripts = ok(self.novel_scripts)
        characters = ok(self.novel_characters)

        # Seed mental states from character cards
        character_states = await self.seed_mental_states(characters)
        logger.info(f"Seeded mental states for {len(character_states)} character(s)")

        chapter_plans = ChapterPlan.from_draft(draft, scripts)

        logger.info(f"Generating {len(chapter_plans)} chapter contents with mental states for '{draft.title}'.")
        chapter_contents = await self.create_chapters(
            draft, chapter_plans, characters, self.chapter_guidance, character_states
        )
        if not chapter_contents:
            logger.warn("Mental chapter content generation returned empty or None.")
            return None
        logger.info(f"Successfully generated {len(chapter_contents)} mental chapter content(s).")
        return chapter_contents


class GenerateNovelMentalRAG(NovelComposeMentalRAG, Action):
    """One-step novel generation with RAG writing styles + mental state tracking."""

    novel_outline: Optional[str] = None
    """The prompt used to generate the novel."""

    novel_language: Optional[str] = None
    """The language of the novel."""

    chapter_guidance: Optional[str] = None
    """Guidance for writing chapter."""

    output_key: str = "novel"
    """Key under which the generated novel will be stored in context."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt) -> Novel | None:
        return await self.compose_novel(ok(self.novel_outline), self.novel_language, self.chapter_guidance)


class GenerateChaptersFromScriptsWithMentalRAG(NovelComposeMentalRAG, Action):
    """Generate chapters with RAG writing style injection + mental state tracking.

    Seeds mental states, does RAG style injection into scripts, then generates
    chapters with both augmented styles and psychological context.
    """

    novel_draft: Optional[NovelDraft] = None
    """The novel draft (for language, metadata)."""

    novel_scripts: Optional[List[Script]] = None
    """The list of chapter scripts to expand into full text."""

    novel_characters: Optional[List[CharacterCard]] = None
    """The list of characters to provide context and seed mental states."""

    chapter_guidance: Optional[str] = None
    """Guidance for writing chapter."""

    writing_style_fetch_config: Optional["WritingStyleFetchConfig"] = None
    """Optional fetch configuration override for writing style retrieval."""

    output_key: str = "novel_chapter_contents"
    """Key under which the generated chapter contents will be stored in context."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt) -> List[str] | List[str | None] | None:
        draft = ok(self.novel_draft)
        scripts = ok(self.novel_scripts)
        characters = ok(self.novel_characters)

        # Seed mental states from character cards
        character_states = await self.seed_mental_states(characters)
        logger.info(f"Seeded mental states for {len(character_states)} character(s)")

        chapter_plans = ChapterPlan.from_draft(draft, scripts)

        logger.info(f"Generating {len(chapter_plans)} RAG+mental chapter contents for '{draft.title}'.")
        chapter_contents = await self.create_chapters(
            draft,
            chapter_plans,
            characters,
            self.chapter_guidance,
            character_states,
            writing_style_fetch_config=self.writing_style_fetch_config,
        )
        if not chapter_contents:
            logger.warn("RAG+Mental chapter content generation returned empty or None.")
            return None
        logger.info(f"Successfully generated {len(chapter_contents)} RAG+mental chapter content(s).")
        return chapter_contents

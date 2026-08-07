"""Character state consistency-aware novel generation actions.

These actions use NovelComposeState to maintain physical/circumstantial state
consistency for characters during novel generation. After each chapter is
generated, the raw prose is audited against per-character state histories;
violations trigger ONE regeneration pass and a Character State Board is
injected into subsequent chapter prompts.
"""

from typing import Any, ClassVar, List, Optional

from fabricatio_character.models.character import CharacterCard
from fabricatio_core import Action, logger
from fabricatio_core.utils import ok

from fabricatio_novel.capabilities.novel_state import NovelComposeState, StateChapterContext
from fabricatio_novel.models.draft import NovelDraft
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.scripting import Script


class GenerateNovelState(NovelComposeState, Action):
    """One-step novel generation with character state consistency tracking.

    Calls compose_novel which builds a StateChapterContext, generates chapters
    with state board injection, and audits each chapter's raw prose for state
    violations (regenerating once on failure).
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


class GenerateChaptersFromScriptsWithState(NovelComposeState, Action):
    """Generate chapters with character state consistency auditing.

    Builds a caller-owned StateChapterContext, generates chapters with state
    board injection, and audits each chapter's raw prose for state violations
    (regenerating once on failure).
    """

    novel_draft: Optional[NovelDraft] = None
    """The novel draft (for language, metadata)."""

    novel_scripts: Optional[List[Script]] = None
    """The list of chapter scripts to expand into full text."""

    novel_characters: Optional[List[CharacterCard]] = None
    """The list of characters to track state for."""

    chapter_guidance: Optional[str] = None
    """Guidance for writing chapter."""

    output_key: str = "novel_chapter_contents"
    """Key under which the generated chapter contents will be stored in context."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt) -> List[str] | List[str | None] | None:
        draft = ok(self.novel_draft)
        scripts = ok(self.novel_scripts)
        characters = ok(self.novel_characters)

        # Character state tracking needs no seeding — histories start empty
        context = StateChapterContext()
        logger.info("Seeded character state consistency tracking")

        chapter_plans = ChapterPlan.from_draft(draft, scripts)

        logger.info(f"Generating {len(chapter_plans)} chapter contents with state consistency for '{draft.title}'.")
        chapter_contents = await self.create_chapters(
            draft, chapter_plans, characters, self.chapter_guidance, context=context
        )
        if not chapter_contents:
            logger.warn("State-consistency chapter content generation returned empty or None.")
            return None
        logger.info(f"Successfully generated {len(chapter_contents)} state-consistent chapter content(s).")
        return chapter_contents

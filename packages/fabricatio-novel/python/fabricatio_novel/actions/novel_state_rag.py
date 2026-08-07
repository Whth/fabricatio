"""RAG + state consistency-aware novel generation actions.

These actions use NovelComposeStateRAG to combine writing style RAG injection
with character state consistency tracking. Each chapter's prompt carries the
fetched style docs AND the Character State Board; the raw prose is audited
after generation (regenerating once on state violations).
"""

from typing import Any, ClassVar, List, Optional

from fabricatio_character.models.character import CharacterCard
from fabricatio_core import Action, logger
from fabricatio_core.utils import ok

from fabricatio_novel.capabilities.novel_state_rag import NovelComposeStateRAG, StateRAGChapterContext
from fabricatio_novel.models.draft import NovelDraft
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.models.novel_rag import WritingStyleFetchConfig
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.scripting import Script


class GenerateNovelStateRAG(NovelComposeStateRAG, Action):
    """One-step novel generation with RAG writing styles + character state consistency.

    Calls compose_novel which builds a StateRAGChapterContext (state
    histories start empty; RAG fetch config defaults per render), generates
    chapters with style docs + state board injection, and audits each
    chapter's raw prose for state violations (regenerating once on failure).
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


class GenerateChaptersFromScriptsWithStateRAG(NovelComposeStateRAG, Action):
    """Generate chapters with RAG writing style injection + state consistency auditing.

    Builds a caller-owned ``StateRAGChapterContext`` carrying the RAG fetch
    config / rerank target (state histories start empty); the RAG
    ``prepare_chapter_prompt`` and state ``extra_chapter_prompt_vars`` /
    ``after_chapter_gen`` hooks then compose on the base loop — style docs
    plus Character State Board per chapter, with one regeneration pass on
    state violations.
    """

    novel_draft: Optional[NovelDraft] = None
    """The novel draft (for language, metadata)."""

    novel_scripts: Optional[List[Script]] = None
    """The list of chapter scripts to expand into full text."""

    novel_characters: Optional[List[CharacterCard]] = None
    """The list of characters to track state for."""

    chapter_guidance: Optional[str] = None
    """Guidance for writing chapter."""

    writing_style_requirement: Optional[str] = None
    """Raw user writing-style requirement. Used as the rerank target for fetched
    writing style documents — docs fetched from LanceDB are reranked against this
    query when it is provided."""

    writing_style_fetch_config: Optional[WritingStyleFetchConfig] = None
    """Optional fetch configuration override for writing style retrieval."""

    output_key: str = "novel_chapter_contents"
    """Key under which the generated chapter contents will be stored in context."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt) -> List[str] | List[str | None] | None:
        draft = ok(self.novel_draft)
        scripts = ok(self.novel_scripts)
        characters = ok(self.novel_characters)

        # State histories need no seeding; RAG config threads through the channel
        rag_config = (
            self.writing_style_fetch_config
            if self.writing_style_fetch_config is not None
            else WritingStyleFetchConfig.default()
        )
        if self.writing_style_requirement and self.writing_style_requirement.strip():
            logger.info(f"Writing style requirement: '{self.writing_style_requirement[:80]}'")
        context = StateRAGChapterContext(
            writing_style_fetch_config=rag_config,
            writing_style_requirement=self.writing_style_requirement,
        )
        logger.info("Seeded character state consistency tracking")

        chapter_plans = ChapterPlan.from_draft(draft, scripts)

        logger.info(f"Generating {len(chapter_plans)} RAG+state chapter contents for '{draft.title}'.")
        chapter_contents = await self.create_chapters(
            draft,
            chapter_plans,
            characters,
            self.chapter_guidance,
            context=context,
        )
        if not chapter_contents:
            logger.warn("RAG+State chapter content generation returned empty or None.")
            return None
        logger.info(f"Successfully generated {len(chapter_contents)} RAG+state chapter content(s).")
        return chapter_contents

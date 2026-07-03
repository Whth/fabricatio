"""Novel RAG actions for retrieval-augmented generation."""

from pathlib import Path
from typing import Any, ClassVar, List, Optional, Type

from fabricatio_character.models.character import CharacterCard
from fabricatio_core import Action, logger
from fabricatio_core.utils import ok
from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig
from fabricatio_rag.actions.db import StoreTextFile

from fabricatio_novel.capabilities.novel_rag import NovelComposeRAG
from fabricatio_novel.models.draft import NovelDraft
from fabricatio_novel.models.novel_rag import (
    WritingStyleDocument,
    WritingStyleFetchConfig,
)
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.scripting import Script


class GenerateChaptersFromScriptsWithRAG(NovelComposeRAG, Action):
    """Generate chapter contents from scripts with RAG writing style augmentation.

    Mirrors GenerateChaptersFromScripts but inherits NovelComposeRAG so that
    create_chapters() applies script-level and scene-level style injection
    before generating prose. Passes writing_style_fetch_config through kwargs.
    """

    novel_draft: Optional[NovelDraft] = None
    """The novel draft (for language, metadata)."""

    novel_scripts: Optional[List[Script]] = None
    """The list of chapter scripts to expand into full text."""

    novel_characters: Optional[List[CharacterCard]] = None
    """The list of characters to provide context."""

    chapter_guidance: Optional[str] = None
    """Guidance for writing chapter."""
    writing_style_query: Optional[str] = None
    """Query text for writing style retrieval. Used to build default fetch config."""

    writing_style_fetch_config: Optional[WritingStyleFetchConfig] = None
    """Optional fetch configuration override for writing style retrieval."""

    use_reranker: bool = False
    """When True, embedding search fetches limit * rerank_scale_factor docs, then reranks to limit."""

    output_key: str = "novel_chapter_contents"
    """Key under which the generated chapter contents will be stored in context."""

    ctx_override: ClassVar[bool] = True

    async def _execute(
        self, *_: Any, **cxt: Any
    ) -> List[str] | List[str | None] | None:
        """Generate chapters with RAG-augmented writing style injection."""
        draft = ok(self.novel_draft)
        scripts = ok(self.novel_scripts)
        characters = ok(self.novel_characters)

        chapter_plans = ChapterPlan.from_draft(draft, scripts)

        # Build config: use explicit override, or build from query, or default
        rag_config = self.writing_style_fetch_config
        if rag_config is None and self.writing_style_query:
            rag_config = WritingStyleFetchConfig()

        logger.info(
            f"Generating {len(chapter_plans)} RAG-augmented chapter contents for '{draft.title}'."
        )
        chapter_contents = await self.create_chapters(
            draft,
            chapter_plans,
            characters,
            self.chapter_guidance,
            writing_style_fetch_config=rag_config,
            use_reranker=self.use_reranker,
        )
        if not chapter_contents:
            logger.warn("RAG chapter content generation returned empty or None.")
            return None
        logger.info(
            f"Successfully generated {len(chapter_contents)} RAG chapter content(s)."
        )
        return chapter_contents


class StoreWritingStyleTexts(StoreTextFile, NovelComposeRAG):
    """Store writing style reference texts from files into LanceDB.

    Reads text files, splits them into chunks, and indexes them
    in the LanceDB vector store for later RAG retrieval. This is a
    standalone ingestion workflow — it does not generate novel content.
    """

    store_model: Type[WritingStyleDocument] = WritingStyleDocument

    output_key: str = "stored_count"

    store_config: LancedbAddRAGConfig | None = None

    async def _execute(
        self,
        text_files: List[Path],
        *_: Any,
        **cxt,
    ) -> int:
        table_name = None
        if self.store_config:
            table_name = self.store_config.table_name
            self.store_config.rebuild_index = False

        cont = await super()._execute(text_files=text_files, **cxt)
        logger.info("Rebuilding index...")
        await self.rebuild_index(table_name)
        logger.info("Index rebuilt!")
        return cont

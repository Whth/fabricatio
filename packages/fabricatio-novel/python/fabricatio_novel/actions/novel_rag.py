"""Novel RAG actions for retrieval-augmented generation."""

from pathlib import Path
from typing import Any, ClassVar, List, Optional, Type

from fabricatio_character.models.character import CharacterCard
from fabricatio_core import Action, logger
from fabricatio_core.utils import ok, override_kwargs
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
    before generating prose. The `writing_style_query` is the raw user intent
    (e.g. "Hemingway terse prose style") and is used for LanceDB retrieval
    — enable `use_refined_query` on the fetch config (or the
    `WritingStyleFetchConfig` instance) to expand it into multiple semantically
    diverse queries via the LLM before search.
    """

    novel_draft: Optional[NovelDraft] = None
    """The novel draft (for language, metadata)."""

    novel_scripts: Optional[List[Script]] = None
    """The list of chapter scripts to expand into full text."""

    novel_characters: Optional[List[CharacterCard]] = None
    """The list of characters to provide context."""

    chapter_guidance: Optional[str] = None
    """Guidance for writing chapter."""
    writing_style_requirement: Optional[str] = None
    """Raw user writing-style requirement. Used as the rerank target for fetched
    writing style documents — docs fetched from LanceDB are reranked against this
    query when it is provided."""

    writing_style_fetch_config: Optional[WritingStyleFetchConfig] = None
    """Optional fetch configuration override."""

    use_refined_query: Optional[bool] = None
    """Convenience override for `WritingStyleFetchConfig.use_refined_query`. Has no effect
    when `writing_style_fetch_config` is supplied explicitly (use the config field instead).
    Tri-state: None leaves the default (False); True/False toggles refinement on/off."""

    refined_query_count: Optional[int] = None
    """Convenience override for `WritingStyleFetchConfig.refined_query_count`. Ignored when
    `writing_style_fetch_config` is supplied explicitly."""

    output_key: str = "novel_chapter_contents"
    """Key under which the generated chapter contents will be stored in context."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt: Any) -> List[str] | List[str | None] | None:
        """Generate chapters with RAG-augmented writing style injection."""
        draft = ok(self.novel_draft)
        scripts = ok(self.novel_scripts)
        characters = ok(self.novel_characters)

        chapter_plans = ChapterPlan.from_draft(draft, scripts)

        # Build config: explicit override > convenience overrides > default.
        if self.writing_style_fetch_config is not None:
            rag_config = self.writing_style_fetch_config
        else:
            # Collect only the convenience fields the caller explicitly set
            # (non-None), then layer them on top of the default config so any
            # unspecified field still uses its Pydantic default.
            overrides = override_kwargs(
                {},
                use_refined_query=self.use_refined_query,
                refined_query_count=self.refined_query_count,
            )
            # `override_kwargs` keeps every key, even None — drop the unset ones
            # so they don't shadow the config's own defaults.
            overrides = {k: v for k, v in overrides.items() if v is not None}
            rag_config = WritingStyleFetchConfig(**overrides) if overrides else WritingStyleFetchConfig.default()
        if self.writing_style_requirement and self.writing_style_requirement.strip():
            logger.info(f"Writing style requirement: '{self.writing_style_requirement[:80]}'")

        logger.info(f"Generating {len(chapter_plans)} RAG-augmented chapter contents for '{draft.title}'.")
        chapter_contents = await self.create_chapters(
            draft,
            chapter_plans,
            characters,
            self.chapter_guidance,
            writing_style_fetch_config=rag_config,
            writing_style_requirement=self.writing_style_requirement,
        )
        if not chapter_contents:
            logger.warn("RAG chapter content generation returned empty or None.")
            return None
        logger.info(f"Successfully generated {len(chapter_contents)} RAG chapter content(s).")
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

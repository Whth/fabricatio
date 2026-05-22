"""Novel RAG actions for retrieval-augmented generation."""

from pathlib import Path
from typing import Any, ClassVar, List, Optional

from fabricatio_character.models.character import CharacterCard
from fabricatio_core import Action, logger
from fabricatio_core.utils import ok

from fabricatio_novel.capabilities.novel_rag import NovelComposeRAG, WritingStyleDocument, WritingStyleFetchConfig
from fabricatio_novel.models.draft import NovelDraft
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.scripting import Script


class RetrieveWritingStyles(NovelComposeRAG, Action):
    """Retrieve writing style documents from LanceDB based on a query."""

    writing_style_query: Optional[str] = None
    """The query text used to search for relevant writing style documents."""

    writing_style_fetch_config: Optional[WritingStyleFetchConfig] = None
    """Optional fetch configuration override for writing style retrieval."""
    output_key: str = "writing_styles"
    """Key under which the retrieved writing style documents will be stored in context."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt: Any) -> List[WritingStyleDocument]:
        """Fetch writing style documents matching the query."""
        query = ok(self.writing_style_query, "`writing_style_query` is required for writing style retrieval")
        logger.info(f"Retrieving writing styles for query: {query[:100]}...")
        docs = await self.afetch_document(query, self.writing_style_fetch_config or WritingStyleFetchConfig.default())
        logger.info(f"Retrieved {len(docs)} writing style document(s)")
        return docs


class InjectWritingStyleToScript(NovelComposeRAG, Action):
    """Inject retrieved writing style documents into scripts.

    Handles both script-level (global_prompt) and scene-level (per-scene prompt)
    injection. Script-level uses the provided `writing_styles`; scene-level fetches
    per-scene docs from LanceDB based on each scene's description.
    """

    novel_scripts: Optional[List[Script]] = None
    """The list of chapter scripts to augment with writing style guidance."""

    writing_styles: Optional[List[WritingStyleDocument]] = None
    """Global writing style documents to inject into each script's global_prompt."""
    writing_style_fetch_config: Optional[WritingStyleFetchConfig] = None
    """Optional fetch configuration override for scene-level writing style retrieval."""

    output_key: str = "novel_scripts"
    """Key under which the augmented scripts will be stored in context (overwrites original)."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt: Any) -> List[Script]:
        """Inject writing styles into script-level and scene-level prompts."""
        scripts = ok(self.novel_scripts, "`novel_scripts` is required for writing style injection")
        global_docs = ok(self.writing_styles, "`writing_styles` is required for injection")
        config = self.writing_style_fetch_config or WritingStyleFetchConfig.default()

        logger.info(f"Injecting {len(global_docs)} global writing style(s) into {len(scripts)} script(s)")

        for script in scripts:
            # Script-level: inject global writing styles
            for doc in global_docs:
                script.append_global_prompt(doc.as_prompt())

            # Scene-level: fetch per-scene based on each scene's description
            for scene in script.scenes:
                scene_docs: List[WritingStyleDocument] = list(ok(await self.afetch_document(scene.description, config)))
                for doc in scene_docs:
                    scene.append_prompt(doc.as_prompt())

        logger.info("Writing style injection complete")
        return scripts


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

    output_key: str = "novel_chapter_contents"
    """Key under which the generated chapter contents will be stored in context."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt: Any) -> List[str] | List[str | None] | None:
        """Generate chapters with RAG-augmented writing style injection."""
        draft = ok(self.novel_draft)
        scripts = ok(self.novel_scripts)
        characters = ok(self.novel_characters)

        chapter_plans = ChapterPlan.from_draft(draft, scripts)

        # Build config: use explicit override, or build from query, or default
        rag_config = self.writing_style_fetch_config
        if rag_config is None and self.writing_style_query:
            rag_config = WritingStyleFetchConfig()

        logger.info(f"Generating {len(chapter_plans)} RAG-augmented chapter contents for '{draft.title}'.")
        chapter_contents = await self.create_chapters(
            draft,
            chapter_plans,
            characters,
            self.chapter_guidance,
            writing_style_fetch_config=rag_config,
        )
        if not chapter_contents:
            logger.warn("RAG chapter content generation returned empty or None.")
            return None
        logger.info(f"Successfully generated {len(chapter_contents)} RAG chapter content(s).")
        return chapter_contents


class StoreWritingStyleTexts(NovelComposeRAG, Action):
    """Store writing style reference texts from files into LanceDB.

    Reads text files, splits them into chunks, and indexes them
    in the LanceDB vector store for later RAG retrieval. This is a
    standalone ingestion workflow — it does not generate novel content.
    """

    files: Optional[List[Path]] = None
    """List of text file paths to ingest as writing style references."""

    chunks_size: int = 512
    """Maximum words per chunk when splitting files."""

    overlap: float = 0.3
    """Overlap ratio between consecutive chunks (0.0–1.0)."""

    output_key: str = "stored_count"
    """Key under which the count of ingested files will be stored in context."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt: Any) -> int:
        """Ingest files into LanceDB as writing style chunks."""
        files = ok(self.files, "`files` is required for storing writing style texts")
        logger.info(
            f"Storing writing style texts from {len(files)} file(s) (chunk_size={self.chunks_size}, overlap={self.overlap})..."
        )
        await self.store_texts(files, self.chunks_size, self.overlap)
        logger.info(f"Successfully stored writing style texts from {len(files)} file(s)")
        return len(files)

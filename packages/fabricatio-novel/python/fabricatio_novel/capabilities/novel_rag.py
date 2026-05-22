"""Novel RAG capabilities combining novel composition with retrieval-augmented generation."""

from abc import ABC
from pathlib import Path
from typing import List, Optional, Self, Sequence, Type, Unpack

from fabricatio_core.rust import split_into_chunks
from fabricatio_core.utils import cfg

cfg(["lancedb"])
from fabricatio_character.models.character import CharacterCard  # noqa: I001
from fabricatio_core import logger

from fabricatio_core.utils import ok
from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig, LancedbFetchRAGConfig, LancedbRAG
from fabricatio_lancedb.models.lancedb import LancedbDocumentModel
from fabricatio_lancedb.rust import SearchedDocument, StoreDocument

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.draft import NovelDraft
from fabricatio_novel.models.kwargs_types import NovelRAGKwargs
from fabricatio_novel.models.plan import ChapterPlan


class WritingStyleDocument(LancedbDocumentModel[StoreDocument, SearchedDocument]):
    """Semantic marker for writing style documents stored in LanceDB."""

    @classmethod
    def from_files(cls, files: Sequence[Path], chunks_size: int = 512, overlap: float = 0.3) -> List[Self]:
        """Create documents by splitting text files into chunks.

        Args:
            files: Sequence of text file paths to read.
            chunks_size: Maximum word count per chunk.
            overlap: Overlap ratio between consecutive chunks (0.0-1.0).

        Returns:
            List of WritingStyleDocument instances, one per chunk.
        """
        return [
            cls(content=c)
            for f in files
            for c in split_into_chunks(f.read_text(encoding="utf-8"), chunks_size, overlap)
        ]


class WritingStyleFetchConfig(LancedbFetchRAGConfig[WritingStyleDocument]):
    """Fetch configuration for writing style documents."""

    document_model: Type[WritingStyleDocument] = WritingStyleDocument
    limit: int = 5
    table_name: str | None = novel_config.writing_styles_table_name


class NovelComposeRAG(
    LancedbRAG[WritingStyleDocument, LancedbAddRAGConfig, WritingStyleFetchConfig], NovelCompose, ABC
):
    """Novel composition capability extended with writing style RAG support."""

    async def create_chapters(
        self,
        draft: NovelDraft,
        chapter_plans: List[ChapterPlan],
        characters: List[CharacterCard],
        guidance: Optional[str] = None,
        **kwargs: Unpack[NovelRAGKwargs[str]],
    ) -> List[str]:
        """Generate chapters with writing style augmentation via RAG.

        Between script generation and chapter generation, retrieves writing
        style references from LanceDB and injects them into script/scene prompts.
        """
        config = kwargs.get("writing_style_fetch_config") or WritingStyleFetchConfig.default()

        for cp in chapter_plans:
            # Script-level: fetch based on full script content → global_prompt
            script_docs: List[WritingStyleDocument] = list(
                ok(await self.afetch_document(cp.script.as_prompt(), config))
            )
            for doc in script_docs:
                cp.script.append_global_prompt(doc.as_prompt())
            logger.debug(f"Chapter {cp.chapter_index}: injected {len(script_docs)} script-level style(s)")

            # Scene-level: fetch per scene based on scene.description → scene.prompt
            for scene in cp.script.scenes:
                scene_docs: List[WritingStyleDocument] = list(ok(await self.afetch_document(scene.description, config)))
                for doc in scene_docs:
                    scene.append_prompt(doc.as_prompt())

        # Delegate to NovelCompose.create_chapters for actual generation
        return await super().create_chapters(draft, chapter_plans, characters, guidance, **kwargs)

    async def store_texts(self, files: List[Path], chunks_size: int = 512, overlap: float = 0.3) -> None:
        """Chunk and store text files as writing style reference documents in LanceDB.

        Args:
            files: List of text file paths to ingest.
            chunks_size: Maximum word count per chunk.
            overlap: Overlap ratio between consecutive chunks (0.0-1.0).
        """
        chunks = WritingStyleDocument.from_files(files, chunks_size, overlap)

        await self.add_document(chunks)

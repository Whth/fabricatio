"""Writing style fetching document models."""

from pathlib import Path
from typing import List, Self, Sequence, Type

from fabricatio_core.rust import split_into_chunks
from fabricatio_lancedb.capabilities.lancedb import LancedbFetchRAGConfig
from fabricatio_lancedb.models.lancedb import LancedbDocumentModel
from fabricatio_lancedb.rust import SearchedDocument, StoreDocument

from fabricatio_novel.config import novel_config


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

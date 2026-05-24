"""Base class for document models."""

from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import List, Self, Sequence, Type

from fabricatio_capabilities.models.generic import AsPrompt
from fabricatio_core.models.generic import Base, Vectorizable
from fabricatio_core.rust import split_into_chunks


class StoredDocumentModel[ST](Vectorizable, Base, metaclass=ABCMeta):
    """A base class for document models."""

    @abstractmethod
    def prepare_insertion(self, vector: Sequence[float]) -> ST:
        """Prepares the data for insertion into a vector database."""

    @classmethod
    def from_txt_files[S: "StoredDocumentModel[ST]"](
        cls: Type[S], files: Sequence[Path], chunk_size: int = 512, overlap: float = 0.2
    ) -> List[S]:
        """Create documents by splitting text files into chunks.

        Args:
            files: Sequence of text file paths to read.
            chunk_size: Maximum word count per chunk.
            overlap: Overlap ratio between consecutive chunks (0.0-1.0).

        Returns:
            List of text chunk document model instances, one per chunk.
        """
        return [
            cls.with_text_chunk(chunk=c)
            for f in files
            for c in split_into_chunks(f.read_text(encoding="utf-8"), chunk_size, overlap)
        ]

    @classmethod
    def with_text_chunk(cls, chunk: str) -> Self:
        """Create with a text chunk."""
        raise NotImplementedError("Subclasses must implement with_text_chunk to support creation from text chunks.")


class SearchedDocumentModel[SD](AsPrompt, Base, metaclass=ABCMeta):
    """A base class for document models retrieved from a vector database."""

    @classmethod
    @abstractmethod
    def from_raw(cls, raw: SD) -> Self:
        """Create the searched model from the rawdata searched from the db."""

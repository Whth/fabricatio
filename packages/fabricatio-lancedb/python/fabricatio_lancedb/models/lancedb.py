"""This module contains the models for the lancedb."""

from typing import Any, Dict, Self, Sequence

from fabricatio_rag.models.document import SearchedDocumentModel, StoredDocumentModel

from fabricatio_lancedb.rust import SearchedDocument, StoreDocument


class LancedbDocumentModel[ST: StoreDocument, SR: SearchedDocument](StoredDocumentModel[ST], SearchedDocumentModel):
    """LanceDB-specific document model extending the base DocumentModel."""

    content: str

    metadata: dict[str, Any] | None = None

    def _prepare_vectorization_inner(self) -> str:
        return self.content

    def prepare_insertion(self, vector: Sequence[float]) -> ST:
        """Prepares the data for insertion into LanceDB."""
        return StoreDocument.with_metadata(content=self.content, metadata=self.metadata, vector=vector)

    @classmethod
    def from_raw(cls, raw: SR) -> Self:
        """Create a document model from a raw LanceDB search result."""
        return cls(content=raw.content, metadata=raw.access_metadata())

    def _as_prompt_inner(self) -> Dict[str, str] | Dict[str, Any] | Any:
        return self.model_dump(exclude_none=True)

    @classmethod
    def with_text_chunk(cls, chunk: str) -> Self:
        """Create a document model instance from a plain text chunk."""
        return cls(content=chunk)

"""This module contains the models for the lancedb."""

from typing import Any, Sequence

from fabricatio_rag.models.document import StoredDocumentModel

from fabricatio_lancedb.rust import StoreDocument


class LancedbStoredDocumentModel[ST: StoreDocument](StoredDocumentModel[ST]):
    """LanceDB-specific document model extending the base DocumentModel."""

    content: str

    metadata: dict[str, Any] | None = None

    def _prepare_vectorization_inner(self) -> str:
        return self.content

    def prepare_insertion(self, vector: Sequence[float]) -> ST:
        """Prepares the data for insertion into LanceDB."""
        return StoreDocument.with_metadata(content=self.content, metadata=self.metadata, vector=vector)

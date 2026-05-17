"""This module contains the models for the lancedb."""

from typing import Sequence

from fabricatio_rag.models.document import DocumentModel

from fabricatio_lancedb.rust import StoreDocument


class LancedbDocumentModel[ST: StoreDocument](DocumentModel[ST]):
    """LanceDB-specific document model extending the base DocumentModel."""

    def prepare_insertion(self, vector: Sequence[float]) -> ST: ...

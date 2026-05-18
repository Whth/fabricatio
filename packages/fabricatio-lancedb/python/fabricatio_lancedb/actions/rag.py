"""LanceDB-specific RAG actions."""

from typing import Any, Self

from fabricatio_core.models.generic import Action
from fabricatio_rag.models.document import StoredDocumentModel

from fabricatio_lancedb.capabilities.lancedb import LancedbRAG
from fabricatio_lancedb.rust import StoreDocument, VectorStoreService


class InjectToDB(Action, LancedbRAG):
    """Inject data into the LanceDB vector store."""

    _svc: VectorStoreService | None = None
    _table_name: str | None = None

    async def _ensure_service(self, uri: str) -> VectorStoreService:
        """Ensure a LanceDB service connection exists."""
        if self._svc is None:
            self._svc = await VectorStoreService.connect(uri)
        return self._svc

    async def add_document(self, data: Any, **kwargs: Any) -> Self:
        """Vectorize and add documents to the store."""
        svc = self._svc
        assert svc is not None, "Call _ensure_service first"

        table_name = kwargs.get("table_name", self._table_name)
        assert table_name is not None, "table_name must be provided"

        ndim = kwargs.get("ndim", 768)
        table = await svc.create_or_open_table(table_name, ndim)

        docs = data if isinstance(data, list) else [data]
        vectors = [await self.vectorize(doc.prepare_vectorization(), send_to="embedding") for doc in docs]
        store_docs = [
            StoreDocument.with_metadata(doc.content, vec, doc.metadata if doc.metadata else None)
            for doc, vec in zip(docs, vectors, strict=True)
        ]
        await table.add_documents(store_docs)
        return self

    async def afetch_document(
        self,
        query: list[str] | str,
        document_model: type[StoredDocumentModel],
        **kwargs: Any,
    ) -> list[StoredDocumentModel]:
        """Search the store and return DocumentModel instances."""
        svc = self._svc
        assert svc is not None, "Call _ensure_service first"

        table_name = kwargs.get("table_name", self._table_name)
        assert table_name is not None, "table_name must be provided"

        ndim = kwargs.get("ndim", 768)
        table = await svc.create_or_open_table(table_name, ndim)

        query_str = query[0] if isinstance(query, list) else query
        embedding = await self.vectorize(query_str, send_to="embedding")
        limit = kwargs.get("limit", 5)
        results = await table.search_document(embedding, limit=limit)
        return [document_model(content=r.content, metadata={}) for r in results]

    @property
    def collection_name(self) -> str:
        """Return the collection/table name."""
        assert self._table_name is not None
        return self._table_name


class LancedbRAGTalk(Action, LancedbRAG):
    """RAG-enabled conversational action for LanceDB."""

    async def aact(self, *args: Any, **kwargs: Any) -> Any:
        """Process user question with RAG context."""
        question = kwargs.get("question", "")
        return await self.afetch_document(question, StoredDocumentModel, **kwargs)

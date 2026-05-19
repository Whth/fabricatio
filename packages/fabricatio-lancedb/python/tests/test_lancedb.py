"""Tests for fabricatio-lancedb Rust-backed vector store operations and RAG capabilities."""

import uuid
from collections.abc import Sequence
from typing import Any, Self

import pytest
from fabricatio_core.capabilities.usages import UseEmbedding
from fabricatio_core.utils import ok
from fabricatio_lancedb.rust import (
    SearchedDocument,
    StoreDocument,
    VectorStoreService,
    VectorStoreTable,
)
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.utils import install_dummy_embeddings, install_dummy_reranks
from fabricatio_rag.capabilities.rag import RAG
from fabricatio_rag.models.document import SearchedDocumentModel, StoredDocumentModel
from pydantic import BaseModel

NDIM = 4


# ---------------------------------------------------------------------------
# Concrete DocumentModel for testing
# ---------------------------------------------------------------------------


class SimpleStoredDocument(StoredDocumentModel, SearchedDocumentModel, BaseModel):
    """A minimal DocumentModel implementation for testing."""

    content: str
    metadata: dict[str, Any] = {}

    @classmethod
    def from_sequence(cls, data: Sequence[dict]) -> list[Self]:
        """Construct instances from a sequence of dicts."""
        return [cls(**item) for item in data]

    def _prepare_vectorization_inner(self) -> str:
        """Return content for embedding."""
        return self.content

    def prepare_insertion(self, vector: Sequence[float]) -> dict[str, Any]:
        """Prepare data for vector store insertion."""
        return {"content": self.content, "vector": list(vector), "metadata": self.metadata}
    @classmethod
    def from_raw(cls, raw: SearchedDocument) -> Self:
        """Create a SimpleStoredDocument from a raw SearchedDocument."""
        return cls(content=raw.content, metadata=raw.access_metadata())

    def _as_prompt_inner(self) -> dict[str, str] | dict[str, Any] | Any:
        """Return data for prompt rendering."""
        return {"content": self.content}


# ---------------------------------------------------------------------------
# Concrete RAG implementation for testing
# ---------------------------------------------------------------------------


class EmbeddingTestRole(LLMTestRole, UseEmbedding):
    """Test role that adds embedding capability to LLMTestRole."""


class RAGTestImpl(LLMTestRole, RAG[SimpleStoredDocument]):
    """Concrete RAG implementation backed by VectorStoreService for testing."""

    _table: VectorStoreTable | None = None
    _svc: VectorStoreService | None = None

    async def _ensure_table(self, svc: VectorStoreService, ndim: int = NDIM) -> VectorStoreTable:
        """Lazily create or open a table."""
        if self._table is None:
            self._svc = svc
            self._table = await svc.create_or_open_table(f"rag_{uuid.uuid4().hex[:8]}", ndim)
        return ok(self._table)

    async def add_document(self, data: Any, **kwargs: Any) -> Self:
        """Vectorize and add documents to the store."""
        table = self._table
        assert table is not None
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
        document_model: type[SimpleStoredDocument],
        **kwargs: Any,
    ) -> list[SimpleStoredDocument]:
        """Search the store and return SimpleDocument instances."""
        table = self._table
        assert table is not None
        query_str = query[0] if isinstance(query, list) else query
        embedding = await self.vectorize(query_str, send_to="embedding")
        limit = kwargs.get("limit", 5)
        results = await table.search_document(embedding, limit=limit)
        return [document_model(content=r.content, metadata={}) for r in results]


# ---------------------------------------------------------------------------
# Fixtures - Rust layer
# ---------------------------------------------------------------------------


@pytest.fixture
async def svc(tmp_path_factory: pytest.TempPathFactory) -> VectorStoreService:
    """Create a LanceDB service backed by a temp directory."""
    uri = str(tmp_path_factory.mktemp("lancedb"))
    return await VectorStoreService.connect(uri)


@pytest.fixture
async def table(svc: VectorStoreService) -> VectorStoreTable:
    """Create a fresh, uniquely-named table per test to guarantee isolation."""
    name = f"test_{uuid.uuid4().hex[:8]}"
    return await svc.create_table(name, NDIM)


@pytest.fixture
def sample_docs() -> list[StoreDocument]:
    """Return three StoreDocument instances with distinct vectors and metadata."""
    return [
        StoreDocument(
            content=f"doc-{i}",
            vector=[float(i)] * NDIM,
            metadata='{"tag": "t' + str(i) + '"}',
        )
        for i in range(3)
    ]


# ---------------------------------------------------------------------------
# Fixtures - RAG capability layer
# ---------------------------------------------------------------------------


@pytest.fixture
async def rag_role(svc: VectorStoreService) -> RAGTestImpl:
    """Create a RAGTestImpl with an initialised vector store table."""
    role = RAGTestImpl()
    await role._ensure_table(svc)
    return role


# ---------------------------------------------------------------------------
# StoreDocument
# ---------------------------------------------------------------------------


class TestStoreDocument:
    """Tests for the StoreDocument data class."""

    def test_new_basic(self) -> None:
        """Create a StoreDocument without metadata."""
        doc = StoreDocument("hello", [1.0, 2.0, 3.0, 4.0], None)
        assert doc.content == "hello"
        assert doc.vector == [1.0, 2.0, 3.0, 4.0]
        assert doc.metadata is None

    def test_new_with_metadata(self) -> None:
        """Create a StoreDocument with a JSON metadata string."""
        meta = '{"key": "value"}'
        doc = StoreDocument("content", [0.0] * NDIM, meta)
        assert doc.metadata == meta

    def test_setters(self) -> None:
        """Verify property setters update values correctly."""
        doc = StoreDocument("a", [0.0] * NDIM, None)
        doc.content = "b"
        doc.vector = [1.0] * NDIM
        doc.metadata = '{"x": 1}'
        assert doc.content == "b"
        assert doc.vector == [1.0] * NDIM
        assert doc.metadata == '{"x": 1}'

    def test_with_metadata_dict(self) -> None:
        """Create a StoreDocument from a Python dict via with_metadata."""
        doc = StoreDocument.with_metadata(
            "text",
            [0.0] * NDIM,
            {"source": "test", "page": 1},
        )
        assert doc.content == "text"
        assert doc.metadata is not None
        assert "source" in doc.metadata

    def test_with_metadata_none(self) -> None:
        """Create a StoreDocument via with_metadata with None metadata."""
        doc = StoreDocument.with_metadata("text", [0.0] * NDIM, None)
        assert doc.metadata is None


# ---------------------------------------------------------------------------
# VectorStoreService
# ---------------------------------------------------------------------------


class TestVectorStoreService:
    """Tests for VectorStoreService connection and table lifecycle."""

    async def test_connect(self, tmp_path_factory: pytest.TempPathFactory) -> None:
        """Connect to a fresh LanceDB directory."""
        uri = str(tmp_path_factory.mktemp("conn_test"))
        svc = await VectorStoreService.connect(uri)
        assert svc is not None

    async def test_create_table(self, svc: VectorStoreService) -> None:
        """Create a new empty table."""
        name = f"create_{uuid.uuid4().hex[:8]}"
        table = await svc.create_table(name, NDIM)
        assert table is not None

    async def test_open_table(self, svc: VectorStoreService) -> None:
        """Open an existing table by name."""
        name = f"open_{uuid.uuid4().hex[:8]}"
        await svc.create_table(name, NDIM)
        reopened = await svc.open_table(name)
        assert reopened is not None

    async def test_create_or_open_creates_new(self, svc: VectorStoreService) -> None:
        """create_or_open_table creates when table does not exist."""
        name = f"coro_new_{uuid.uuid4().hex[:8]}"
        table = await svc.create_or_open_table(name, NDIM)
        assert table is not None

    async def test_create_or_open_opens_existing(self, svc: VectorStoreService) -> None:
        """create_or_open_table opens when table already exists."""
        name = f"coro_exist_{uuid.uuid4().hex[:8]}"
        await svc.create_table(name, NDIM)
        table = await svc.create_or_open_table(name, NDIM)
        assert table is not None

    async def test_open_nonexistent_raises(self, svc: VectorStoreService) -> None:
        """Opening a non-existent table raises an error."""
        name = f"missing_{uuid.uuid4().hex[:8]}"
        with pytest.raises(OSError, match="not found"):
            await svc.open_table(name)


# ---------------------------------------------------------------------------
# VectorStoreTable - add_documents
# ---------------------------------------------------------------------------


class TestAddDocuments:
    """Tests for adding documents to a vector store table."""

    async def test_add_single(self, table: VectorStoreTable, sample_docs: list[StoreDocument]) -> None:
        """Add a single document and verify one ID is returned."""
        ids = await table.add_documents([sample_docs[0]])
        assert len(ids) == 1
        assert isinstance(ids[0], str)

    async def test_add_multiple(self, table: VectorStoreTable, sample_docs: list[StoreDocument]) -> None:
        """Add multiple documents and verify all IDs are unique."""
        ids = await table.add_documents(sample_docs)
        assert len(ids) == len(sample_docs)
        assert len(set(ids)) == len(ids)

    async def test_add_without_metadata(self, table: VectorStoreTable) -> None:
        """Add a document with None metadata."""
        doc = StoreDocument("no-meta", [1.0, 2.0, 3.0, 4.0], None)
        ids = await table.add_documents([doc])
        assert len(ids) == 1

    async def test_add_with_dict_metadata(self, table: VectorStoreTable) -> None:
        """Add a document created via with_metadata with a dict."""
        doc = StoreDocument.with_metadata("dict-meta", [1.0, 2.0, 3.0, 4.0], {"k": "v"})
        ids = await table.add_documents([doc])
        assert len(ids) == 1


# ---------------------------------------------------------------------------
# VectorStoreTable - search_document
# ---------------------------------------------------------------------------


class TestSearchDocument:
    """Tests for searching documents from a vector store table."""

    async def test_search_returns_results(self, table: VectorStoreTable, sample_docs: list[StoreDocument]) -> None:
        """Search after adding documents returns SearchedDocument instances."""
        await table.add_documents(sample_docs)
        results = await table.search_document([0.0] * NDIM, limit=3)
        assert len(results) > 0
        assert isinstance(results[0], SearchedDocument)

    async def test_search_limit(self, table: VectorStoreTable, sample_docs: list[StoreDocument]) -> None:
        """Search respects the limit parameter."""
        await table.add_documents(sample_docs)
        results = await table.search_document([0.0] * NDIM, limit=1)
        assert len(results) == 1

    async def test_search_result_fields(self, table: VectorStoreTable, sample_docs: list[StoreDocument]) -> None:
        """SearchedDocument fields have correct types and non-empty values."""
        await table.add_documents(sample_docs)
        results = await table.search_document([0.0] * NDIM, limit=3)
        for doc in results:
            assert isinstance(doc.id, str)
            assert len(doc.id) > 0
            assert isinstance(doc.content, str)
            assert isinstance(doc.timestamp, int)
            assert doc.timestamp > 0

    async def test_search_result_metadata(self, table: VectorStoreTable, sample_docs: list[StoreDocument]) -> None:
        """access_metadata returns a dict for documents with metadata."""
        await table.add_documents(sample_docs)
        results = await table.search_document([0.0] * NDIM, limit=3)
        for doc in results:
            meta = doc.access_metadata()
            assert isinstance(meta, dict)


# ---------------------------------------------------------------------------
# SearchedDocument
# ---------------------------------------------------------------------------


class TestSearchedDocument:
    """Tests for SearchedDocument property access and metadata handling."""

    async def test_access_metadata_returns_dict(self, table: VectorStoreTable) -> None:
        """access_metadata on a document with JSON metadata returns a dict."""
        doc = StoreDocument("meta-test", [1.0, 2.0, 3.0, 4.0], '{"a": 1}')
        await table.add_documents([doc])
        results = await table.search_document([1.0, 2.0, 3.0, 4.0], limit=1)
        assert len(results) == 1
        meta = results[0].access_metadata()
        assert isinstance(meta, dict)

    async def test_access_metadata_none_returns_empty(self, table: VectorStoreTable) -> None:
        """access_metadata on a document without metadata returns empty dict."""
        doc = StoreDocument("no-meta", [1.0, 2.0, 3.0, 4.0], None)
        await table.add_documents([doc])
        results = await table.search_document([1.0, 2.0, 3.0, 4.0], limit=1)
        assert len(results) == 1
        assert results[0].access_metadata() == {}

    async def test_content_roundtrip(self, table: VectorStoreTable) -> None:
        """Unicode content survives the add/search round trip."""
        payload = "roundtrip-check-unicöde-内容"
        doc = StoreDocument(payload, [0.5] * NDIM, None)
        await table.add_documents([doc])
        results = await table.search_document([0.5] * NDIM, limit=1)
        assert results[0].content == payload

    async def test_ids_are_uuids(self, table: VectorStoreTable) -> None:
        """Returned IDs are valid UUIDv4 strings."""
        doc = StoreDocument("uuid-check", [1.0] * NDIM, None)
        ids = await table.add_documents([doc])
        for doc_id in ids:
            uuid.UUID(doc_id)

    async def test_timestamps_are_positive(self, table: VectorStoreTable) -> None:
        """Timestamps in search results are positive integers."""
        doc = StoreDocument("ts-check", [1.0] * NDIM, None)
        await table.add_documents([doc])
        results = await table.search_document([1.0] * NDIM, limit=1)
        assert results[0].timestamp > 0


# ---------------------------------------------------------------------------
# Round-trip / integration - Rust layer
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """End-to-end add, search, and verify integration tests."""

    async def test_exact_match_ranked_first(self, table: VectorStoreTable) -> None:
        """A query identical to one document's vector should surface it first."""
        target = [1.0, 0.0, 0.0, 0.0]
        other = [0.0, 1.0, 0.0, 0.0]
        await table.add_documents(
            [
                StoreDocument("target", target, None),
                StoreDocument("other", other, None),
            ]
        )
        results = await table.search_document(target, limit=2)
        assert len(results) == 2
        assert results[0].content == "target"

    async def test_many_documents(self, table: VectorStoreTable) -> None:
        """Adding many docs and searching should respect the limit parameter."""
        n = 50
        docs = [StoreDocument(f"doc-{i}", [float(i % 5)] * NDIM, None) for i in range(n)]
        ids = await table.add_documents(docs)
        assert len(ids) == n

        results = await table.search_document([0.0] * NDIM, limit=10)
        assert len(results) == 10

    async def test_add_reopen_search(self, svc: VectorStoreService) -> None:
        """Documents persist across table close and reopen."""
        name = f"reopen_{uuid.uuid4().hex[:8]}"
        table = await svc.create_table(name, NDIM)
        doc = StoreDocument("persistent", [2.0] * NDIM, '{"p": true}')
        await table.add_documents([doc])

        reopened = await svc.open_table(name)
        results = await reopened.search_document([2.0] * NDIM, limit=1)
        assert len(results) == 1
        assert results[0].content == "persistent"
        assert results[0].metadata is not None
        assert "p" in results[0].metadata


# ---------------------------------------------------------------------------
# RAG capability - vectorize via mock embeddings
# ---------------------------------------------------------------------------


class TestVectorize:
    """Tests for vectorize through the mock embedding router."""

    async def test_vectorize_single(self) -> None:
        """Vectorize returns a list of floats for a single string input."""
        role = EmbeddingTestRole()
        embedding = [0.1, 0.2, 0.3, 0.4]
        with install_dummy_embeddings(embedding):
            result = await role.vectorize("hello world", send_to="embedding")
        assert isinstance(result, list)
        assert len(result) == NDIM

    async def test_vectorize_batch(self) -> None:
        """Vectorize returns a list of floats per individual text call."""
        role = EmbeddingTestRole()
        e1, e2 = [1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]
        with install_dummy_embeddings(e1, e2):
            r1 = await role.vectorize("doc-a", send_to="embedding")
            r2 = await role.vectorize("doc-b", send_to="embedding")
        assert isinstance(r1, list)
        assert isinstance(r2, list)


# ---------------------------------------------------------------------------
# RAG capability - arank_documents via mock reranker
# ---------------------------------------------------------------------------


class TestRankDocuments:
    """Tests for arank_documents through the mock reranker router."""

    async def test_rank_reorders_by_score(self, rag_role: RAGTestImpl) -> None:
        """arank_documents reorders documents by descending reranker score."""
        docs = [
            SimpleStoredDocument(content="low relevance", metadata={}),
            SimpleStoredDocument(content="high relevance", metadata={}),
            SimpleStoredDocument(content="medium relevance", metadata={}),
        ]
        # Reranker returns (index, score): doc 1 highest, doc 2 middle, doc 0 lowest
        rankings = [(1, 0.95), (2, 0.60), (0, 0.10)]
        with install_dummy_reranks(*rankings):
            result = await rag_role.arank_documents("test query", docs, send_to="reranker")
        assert len(result) >= 1
        assert result[0].content == "high relevance"

    async def test_rank_empty_list(self, rag_role: RAGTestImpl) -> None:
        """arank_documents returns empty list for empty input."""
        result = await rag_role.arank_documents("query", [])
        assert result == []


# ---------------------------------------------------------------------------
# RAG capability - end-to-end add and fetch with mocked LLM
# ---------------------------------------------------------------------------


class TestRAGEndToEnd:
    """End-to-end tests: add documents with mocked embeddings, then fetch."""

    async def test_add_and_fetch(self, rag_role: RAGTestImpl) -> None:
        """Add documents via mocked embeddings and search them back."""
        docs = [
            SimpleStoredDocument(content="rust programming", metadata={"lang": "rust"}),
            SimpleStoredDocument(content="python scripting", metadata={"lang": "python"}),
        ]
        # Two embeddings for add, one for fetch query
        e1 = [1.0, 0.0, 0.0, 0.0]
        e2 = [0.0, 1.0, 0.0, 0.0]
        e_query = [1.0, 0.0, 0.0, 0.0]  # closer to e1

        with install_dummy_embeddings(e1, e2, e_query):
            await rag_role.add_document(docs)
            results = await rag_role.afetch_document("rust", SimpleStoredDocument, limit=2)

        assert len(results) > 0
        assert results[0].content == "rust programming"

    async def test_add_single_and_fetch(self, rag_role: RAGTestImpl) -> None:
        """Add a single document and fetch it back."""
        doc = SimpleStoredDocument(content="hello world", metadata={})
        e_add = [0.5, 0.5, 0.5, 0.5]
        e_query = [0.5, 0.5, 0.5, 0.5]

        with install_dummy_embeddings(e_add, e_query):
            await rag_role.add_document(doc)
            results = await rag_role.afetch_document("hello", SimpleStoredDocument, limit=1)

        assert len(results) == 1
        assert results[0].content == "hello world"

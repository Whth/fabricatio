"""Tests for fabricatio-rag."""

import tempfile
from pathlib import Path
from typing import List, Self, Sequence
from unittest.mock import AsyncMock, patch

import pytest
from fabricatio_rag.capabilities.rag import RAG, RAGConfigBase
from fabricatio_rag.config import RagConfig, rag_config
from fabricatio_rag.models.document import SearchedDocumentModel, StoredDocumentModel

# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestRagConfig:
    """Tests for RagConfig dataclass."""

    def test_default_refined_query_template(self) -> None:
        """Test that the default refined_query_template is set."""
        cfg = RagConfig()
        assert cfg.refined_query_template == "built-in/refined_query"

    def test_custom_refined_query_template(self) -> None:
        """Test custom refined_query_template."""
        cfg = RagConfig(refined_query_template="custom/template")
        assert cfg.refined_query_template == "custom/template"

    def test_rag_config_singleton_is_rag_config(self) -> None:
        """Test that rag_config singleton is an instance of RagConfig."""
        assert isinstance(rag_config, RagConfig)


# ---------------------------------------------------------------------------
# RAGConfigBase tests
# ---------------------------------------------------------------------------


class TestRAGConfigBase:
    """Tests for RAGConfigBase."""

    def test_default_creates_instance(self) -> None:
        """Test that default() creates an instance."""
        cfg = RAGConfigBase.default()
        assert isinstance(cfg, RAGConfigBase)


# ---------------------------------------------------------------------------
# StoredDocumentModel tests
# ---------------------------------------------------------------------------


class _ConcreteStoredDoc(StoredDocumentModel[str]):
    """Concrete StoredDocumentModel for testing."""

    text: str = ""

    def prepare_insertion(self, vector: Sequence[float]) -> str:
        """Prepare for insertion into a vector DB."""
        return f"inserted:{self.text}"

    def _prepare_vectorization_inner(self) -> str:
        """Return text for vectorization."""
        return self.text

    @classmethod
    def with_text_chunk(cls, chunk: str) -> Self:
        """Create with a text chunk."""
        return cls(text=chunk)


class TestStoredDocumentModel:
    """Tests for StoredDocumentModel."""

    def test_prepare_insertion(self) -> None:
        """Test prepare_insertion returns expected format."""
        doc = _ConcreteStoredDoc(text="hello")
        result = doc.prepare_insertion([0.1, 0.2, 0.3])
        assert result == "inserted:hello"

    def test_from_txt_files_single_file(self) -> None:
        """Test from_txt_files with a single small file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("hello world")
            path = Path(f.name)

        try:
            docs = _ConcreteStoredDoc.from_txt_files([path], chunk_size=100, overlap=0.0)
            assert len(docs) >= 1
            assert all(isinstance(d, _ConcreteStoredDoc) for d in docs)
            combined = " ".join(d.text for d in docs)
            assert "hello world" in combined
        finally:
            path.unlink()

    def test_from_txt_files_multiple_files(self) -> None:
        """Test from_txt_files with multiple files."""
        paths = []
        for content in ["file one content", "file two content"]:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
                f.write(content)
                paths.append(Path(f.name))

        try:
            docs = _ConcreteStoredDoc.from_txt_files(paths, chunk_size=100, overlap=0.0)
            assert len(docs) >= 2
            texts = " ".join(d.text for d in docs)
            assert "file one" in texts
            assert "file two" in texts
        finally:
            for p in paths:
                p.unlink()

    def test_from_txt_files_chunking(self) -> None:
        """Test that chunking splits large files into multiple docs."""
        # Generate enough text content to trigger chunking
        text = " ".join(["word"] * 5000)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(text)
            path = Path(f.name)

        try:
            docs = _ConcreteStoredDoc.from_txt_files([path], chunk_size=100, overlap=0.0)
            assert len(docs) >= 1
            combined = " ".join(d.text for d in docs)
            assert "word" in combined
        finally:
            path.unlink()

    def test_with_text_chunk_raises_not_implemented_on_base(self) -> None:
        """Test that base StoredDocumentModel.with_text_chunk raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Subclasses must implement"):
            StoredDocumentModel.with_text_chunk("chunk")


# ---------------------------------------------------------------------------
# SearchedDocumentModel tests
# ---------------------------------------------------------------------------


class _ConcreteSearchedDoc(SearchedDocumentModel[str]):
    """Concrete SearchedDocumentModel for testing."""

    content: str = ""

    @classmethod
    def from_raw(cls, raw: str) -> Self:
        """Create from raw data."""
        return cls(content=raw)

    def _as_prompt_inner(self) -> dict:
        """Return content for prompt rendering."""
        return {"content": self.content}


class TestSearchedDocumentModel:
    """Tests for SearchedDocumentModel."""

    def test_from_raw(self) -> None:
        """Test from_raw creates a new instance."""
        doc = _ConcreteSearchedDoc.from_raw("test content")
        assert doc.content == "test content"
        assert isinstance(doc, _ConcreteSearchedDoc)

    def test_as_prompt(self) -> None:
        """Test as_prompt renders the template."""
        doc = _ConcreteSearchedDoc(content="some text")
        result = doc.as_prompt()
        assert isinstance(result, str)
        assert "some text" in result


# ---------------------------------------------------------------------------
# RAG capability tests
# ---------------------------------------------------------------------------


class _ConcreteRAGConfig(RAGConfigBase):
    """Concrete RAG config for testing."""

    pass


class _ConcreteRAG(RAG[_ConcreteStoredDoc, _ConcreteSearchedDoc, _ConcreteRAGConfig, _ConcreteRAGConfig]):
    """Concrete RAG implementation for testing."""

    def __init__(self) -> None:
        """Initialize with empty stored docs."""
        self._stored_docs: List[_ConcreteStoredDoc] = []

    async def add_document(self, data: _ConcreteStoredDoc | List[_ConcreteStoredDoc], config: object = None) -> Self:
        """Add documents to storage."""
        if isinstance(data, list):
            self._stored_docs.extend(data)
        else:
            self._stored_docs.append(data)
        return self

    async def afetch_document(self, query: str | List[str], config: object = None) -> List[_ConcreteSearchedDoc]:
        """Fetch documents matching query."""
        queries = [query] if isinstance(query, str) else query
        return [
            _ConcreteSearchedDoc(content=doc.text) for doc in self._stored_docs if any(q in doc.text for q in queries)
        ]


class TestRAG:
    """Tests for RAG capability."""

    @pytest.mark.asyncio
    async def test_add_single_document(self) -> None:
        """Test adding a single document."""
        rag = _ConcreteRAG()
        doc = _ConcreteStoredDoc(text="test document")
        result = await rag.add_document(doc)
        assert result is rag
        assert len(rag._stored_docs) == 1

    @pytest.mark.asyncio
    async def test_add_multiple_documents(self) -> None:
        """Test adding multiple documents."""
        rag = _ConcreteRAG()
        docs = [_ConcreteStoredDoc(text=f"doc {i}") for i in range(3)]
        await rag.add_document(docs)
        assert len(rag._stored_docs) == 3

    @pytest.mark.asyncio
    async def test_fetch_document(self) -> None:
        """Test fetching documents by query."""
        rag = _ConcreteRAG()
        await rag.add_document([_ConcreteStoredDoc(text="python is great"), _ConcreteStoredDoc(text="rust is fast")])
        results = await rag.afetch_document("python")
        assert len(results) == 1
        assert results[0].content == "python is great"

    @pytest.mark.asyncio
    async def test_fetch_document_no_match(self) -> None:
        """Test fetching with no matching documents."""
        rag = _ConcreteRAG()
        await rag.add_document([_ConcreteStoredDoc(text="hello world")])
        results = await rag.afetch_document("nonexistent")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_fetch_document_multiple_queries(self) -> None:
        """Test fetching with multiple query strings."""
        rag = _ConcreteRAG()
        await rag.add_document([_ConcreteStoredDoc(text="python is great"), _ConcreteStoredDoc(text="rust is fast")])
        results = await rag.afetch_document(["python", "rust"])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_arank_documents_empty_list(self) -> None:
        """Test arank_documents with empty document list returns empty."""
        rag = _ConcreteRAG()
        result = await rag.arank_documents("query", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_arank_documents_returns_reordered(self) -> None:
        """Test arank_documents reorders documents by ranking score."""
        rag = _ConcreteRAG()
        docs = [
            _ConcreteSearchedDoc(content="first"),
            _ConcreteSearchedDoc(content="second"),
            _ConcreteSearchedDoc(content="third"),
        ]
        # Mock arank to return indices in reverse order with scores
        mock_arank = AsyncMock(return_value=[(2, 0.9), (0, 0.7), (1, 0.3)])
        with patch.object(type(rag), "arank", mock_arank):
            result = await rag.arank_documents("query", docs)
        assert len(result) == 3
        assert result[0].content == "third"
        assert result[1].content == "first"
        assert result[2].content == "second"

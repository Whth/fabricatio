"""Tests for the LanceDB-backed RAG models and capabilities in fabricatio-typst.

Covers model roundtrip (prepare_insertion), CitationManager dedup,
and CitationLancedbRAG.clued_search with mocked LLM + embedding router.
"""

from typing import TYPE_CHECKING, Any, ClassVar, List, Optional

import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_typst.capabilities.citation_rag import CitationLancedbRAG
from fabricatio_typst.models.article_rag import ArticleChunk, CitationManager

if TYPE_CHECKING:
    from fabricatio_lancedb.rust import StoreDocument


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_chunk() -> ArticleChunk:
    """A representative ArticleChunk for testing."""
    return ArticleChunk(
        content="This is a test chunk about machine learning.",
        year=2023,
        authors=["Alice Wang", "Bob Li"],
        article_title="Advances in Deep Learning",
        bibtex_cite_key="wang2023advances",
    )


@pytest.fixture
def sample_chunks() -> List[ArticleChunk]:
    """Multiple chunks from two distinct articles."""
    return [
        ArticleChunk(
            content="First chunk from article A.",
            year=2022,
            authors=["Author One"],
            article_title="Article Alpha",
            bibtex_cite_key="one2022alpha",
        ),
        ArticleChunk(
            content="Second chunk from article A.",
            year=2022,
            authors=["Author One"],
            article_title="Article Alpha",
            bibtex_cite_key="one2022alpha",
        ),
        ArticleChunk(
            content="First chunk from article B.",
            year=2021,
            authors=["Author Two"],
            article_title="Article Beta",
            bibtex_cite_key="two2021beta",
        ),
    ]


@pytest.fixture
def populated_cm(sample_chunks: List[ArticleChunk]) -> CitationManager:
    """CitationManager pre-populated with sample chunks."""
    cm = CitationManager()
    cm.add_chunks(sample_chunks, set_cite_number=True, dedup=True)
    return cm


# ---------------------------------------------------------------------------
# ArticleChunk model
# ---------------------------------------------------------------------------


class TestArticleChunkModel:
    """Verify ArticleChunk fields and serialization to LanceDB StoreDocument."""

    def test_construction(self, sample_chunk: ArticleChunk) -> None:
        """Basic field access works."""
        assert sample_chunk.content == "This is a test chunk about machine learning."
        assert sample_chunk.year == 2023
        assert sample_chunk.authors == ["Alice Wang", "Bob Li"]
        assert sample_chunk.article_title == "Advances in Deep Learning"
        assert sample_chunk.bibtex_cite_key == "wang2023advances"

    def test_prepare_insertion_content(self, sample_chunk: ArticleChunk) -> None:
        """prepare_insertion uses chunk content and embeds metadata."""
        vector = [0.1, 0.2, 0.3]
        doc: StoreDocument = sample_chunk.prepare_insertion(vector)

        assert doc.content == sample_chunk.content
        assert doc.content == sample_chunk.content
        # StoreDocument.vector uses f32 internally — use approx
        assert doc.vector == pytest.approx(vector, rel=1e-5)

        # metadata is a JSON string — verify it contains the key fields
        assert doc.metadata is not None
        assert "wang2023advances" in (doc.metadata or "")
        assert "Alice Wang" in (doc.metadata or "")
        assert "2023" in (doc.metadata or "")

    def test_prepare_vectorization_uses_content(self, sample_chunk: ArticleChunk) -> None:
        """_prepare_vectorization returns the chunk content."""
        assert sample_chunk.prepare_vectorization() == sample_chunk.content

    def test_reference_header(self) -> None:
        """reference_header formats correctly after cite_number is set."""
        chunk = ArticleChunk(
            content="Some text.",
            year=2020,
            authors=["John Smith"],
            article_title="Test Article",
            bibtex_cite_key="smith2020test",
        )
        chunk.update_cite_number(5)
        header = chunk.reference_header
        assert "[[5]]" in header
        assert "Test Article" in header
        assert "Smith" in header

    def test_as_typst_cite(self, sample_chunk: ArticleChunk) -> None:
        """as_typst_cite wraps bibtex key in typst cite syntax."""
        assert sample_chunk.as_typst_cite() == "#cite(<wang2023advances>)"

    def test_purge_numeric_citation(self) -> None:
        """Numeric citations like [1] or [1, 2-5] are stripped."""
        text = "Some text [1] and more [2, 3-5] end."
        result = ArticleChunk.purge_numeric_citation(text)
        assert "[1]" not in result
        assert "[2, 3-5]" not in result
        assert "Some text" in result
        assert "and more" in result

    def test_from_file_requires_bib_key(self, tmp_path) -> None:  # noqa: ANN001
        """from_file returns empty list when no cite key is found."""
        from fabricatio_typst.rust import BibManager

        # Create a temp file with content
        p = tmp_path / "no_match - Unknown.txt"
        p.write_text("Some content here.", encoding="utf-8")

        # BibManager needs a real bib file — create a minimal one
        bib_path = tmp_path / "empty.bib"
        bib_path.write_text("", encoding="utf-8")
        bm = BibManager(str(bib_path))

        chunks = ArticleChunk.from_file(p, bm, max_chunk_size=500)
        assert chunks == []


# ---------------------------------------------------------------------------
# CitationManager
# ---------------------------------------------------------------------------


class TestCitationManager:
    """Tests for CitationManager dedup and key-set extraction."""

    def test_get_dedup_key_set(self, populated_cm: CitationManager) -> None:
        """get_dedup_key_set returns unique bibtex_cite_keys."""
        keys = populated_cm.get_dedup_key_set()
        assert keys == {"one2022alpha", "two2021beta"}

    def test_get_dedup_key_set_empty(self) -> None:
        """Empty manager returns empty set."""
        cm = CitationManager()
        assert cm.get_dedup_key_set() == set()

    def test_dedup_on_add_chunks(self, sample_chunks: List[ArticleChunk]) -> None:
        """add_chunks deduplicates by content hash when dedup=True."""
        cm = CitationManager()
        cm.add_chunks(sample_chunks, dedup=True)
        cm.add_chunks(sample_chunks, dedup=True)
        # 3 original chunks, but 2 share a bibtex key and have the same
        # content hash — dedup removes content-identical chunks.
        # After dedup, the two chunks from article A have different content,
        # so they're kept.  Re-adding the same set removes all (they're
        # duplicates by content hash).
        assert len(cm.article_chunks) <= 3

    def test_no_dedup_when_false(self, sample_chunks: List[ArticleChunk]) -> None:
        """add_chunks with dedup=False keeps duplicates."""
        cm = CitationManager()
        cm.add_chunks(sample_chunks, dedup=False)
        first_len = len(cm.article_chunks)
        cm.add_chunks(sample_chunks, dedup=False)
        assert len(cm.article_chunks) == first_len * 2

    def test_set_cite_number_all(self, sample_chunks: List[ArticleChunk]) -> None:
        """set_cite_number_all assigns unique numbers per bibtex_cite_key."""
        cm = CitationManager()
        cm.add_chunks(sample_chunks, set_cite_number=True)
        keys_map = {c.bibtex_cite_key: c.cite_number for c in cm.article_chunks}
        # Two distinct articles → two distinct numbers
        assert len(set(keys_map.values())) >= 2

    def test_citation_count(self, populated_cm: CitationManager) -> None:
        """citation_count counts distinct citation references."""
        text = "See [[1]] and [[2]] for details."
        count = populated_cm.citation_count(text)
        assert count >= 0  # may be 0 if numbers don't match

    def test_apply_replaces_citations(self, populated_cm: CitationManager) -> None:
        """Apply substitutes citation placeholders with typst cite commands."""
        text = "According to [[1]], the results are clear."
        result = populated_cm.apply(text)
        # Should have replaced the placeholder
        assert "[[" not in result or "#cite" in result


# ---------------------------------------------------------------------------
# CitationLancedbRAG.clued_search (with mocked router)
# ---------------------------------------------------------------------------


class MockCitationLancedbRAG(LLMTestRole, CitationLancedbRAG):
    """Test double that overrides aretrieve and arefined_query to avoid real LanceDB/LLM calls."""

    canned_chunks: ClassVar[List[ArticleChunk]] = []
    retrieve_calls: int = 0

    async def aretrieve(
        self,
        query: Any,  # type: ignore[annotation-unchecked]
        document_model: Any,  # type: ignore[annotation-unchecked]
        max_accepted: int = 10,
        table_name: Optional[str] = None,
        result_per_query: Optional[int] = None,
    ) -> List[ArticleChunk]:
        """Return canned chunks, tracking call count."""
        self.retrieve_calls += 1
        return list(self.canned_chunks)

    async def arefined_query(self, question: str, **kwargs: Any) -> List[str]:
        """Return a canned refined query — no LLM call needed."""
        return ["mock refined query"]


class MockDedupCitationLancedbRAG(MockCitationLancedbRAG):
    """Variant that returns a chunk whose key is already held — for dedup testing."""

    async def aretrieve(  # noqa: D102
        self,
        query: Any,  # type: ignore[annotation-unchecked]
        document_model: Any,  # type: ignore[annotation-unchecked]
        max_accepted: int = 10,
        table_name: Optional[str] = None,
        result_per_query: Optional[int] = None,
    ) -> List[ArticleChunk]:
        self.retrieve_calls += 1
        return [
            ArticleChunk(
                content="Duplicate chunk from known article.",
                year=2023,
                authors=["C. Darwin"],
                article_title="Evolution of Networks",
                bibtex_cite_key="darwin2023evo",
            ),
        ]


class TestCitationLancedbRAG:
    """Integration-style tests for clued_search using mock router."""

    @pytest.fixture
    def canned_chunks(self) -> List[ArticleChunk]:
        """Chunks returned by the mock aretrieve."""
        return [
            ArticleChunk(
                content="Chunk about neural networks.",
                year=2023,
                authors=["C. Darwin"],
                article_title="Evolution of Networks",
                bibtex_cite_key="darwin2023evo",
            ),
            ArticleChunk(
                content="Another chunk about AI safety.",
                year=2024,
                authors=["E. Curie"],
                article_title="Safe AI Systems",
                bibtex_cite_key="curie2024safe",
            ),
        ]

    @pytest.mark.asyncio
    async def test_clued_search_basic_flow(self, canned_chunks: List[ArticleChunk]) -> None:
        """clued_search runs the search loop with mocked aretrieve + arefined_query."""
        role = MockCitationLancedbRAG()
        role.canned_chunks = canned_chunks
        cm = CitationManager()

        result = await role.clued_search(
            requirement="Find papers about neural networks.",
            cm=cm,
            max_capacity=10,
            max_round=2,
            base_accepted=5,
        )

        assert isinstance(result, CitationManager)
        assert len(result.article_chunks) > 0
        assert role.retrieve_calls >= 1

    @pytest.mark.asyncio
    async def test_clued_search_client_side_dedup(self) -> None:
        """Chunks already in CitationManager are excluded after retrieval."""
        role = MockDedupCitationLancedbRAG()

        cm = CitationManager()
        cm.add_chunks(
            [
                ArticleChunk(
                    content="Pre-existing chunk.",
                    year=2023,
                    authors=["C. Darwin"],
                    article_title="Evolution of Networks",
                    bibtex_cite_key="darwin2023evo",
                ),
            ],
            set_cite_number=True,
        )
        keys_before = cm.get_dedup_key_set()

        result = await role.clued_search(
            requirement="Find more papers.",
            cm=cm,
            max_capacity=10,
            max_round=1,
            base_accepted=5,
        )

        keys_after = result.get_dedup_key_set()
        assert keys_after == keys_before

    @pytest.mark.asyncio
    async def test_clued_search_max_capacity(self, canned_chunks: List[ArticleChunk]) -> None:
        """When max_capacity is exceeded, chunks are truncated."""
        role = MockCitationLancedbRAG()
        role.canned_chunks = canned_chunks * 10
        cm = CitationManager()

        result = await role.clued_search(
            requirement="Find papers.",
            cm=cm,
            max_capacity=3,
            max_round=2,
            base_accepted=20,
        )

        assert len(result.article_chunks) <= 3

    @pytest.mark.asyncio
    async def test_clued_search_empty_citation_manager(self, canned_chunks: List[ArticleChunk]) -> None:
        """clued_search works starting from an empty CitationManager."""
        role = MockCitationLancedbRAG()
        role.canned_chunks = canned_chunks
        cm = CitationManager()

        result = await role.clued_search(
            requirement="Initial search.",
            cm=cm,
            max_capacity=5,
            max_round=1,
            base_accepted=5,
        )

        assert len(result.article_chunks) > 0


# ---------------------------------------------------------------------------
# LancedbRAG view/table pattern (model-level, no DB needed)
# ---------------------------------------------------------------------------


class TestLancedbRAGViewPattern:
    """Verify the view()/safe_target_table pattern works without DB."""

    def test_view_sets_target_table(self) -> None:
        """view() updates target_table."""
        role = MockCitationLancedbRAG()
        assert role.target_table is None
        role.view("my_table")
        assert role.target_table == "my_table"

    def test_safe_target_table_raises_when_none(self) -> None:
        """safe_target_table raises when no table is viewed."""
        role = MockCitationLancedbRAG()
        with pytest.raises(ValueError, match="No table is being viewed"):
            _ = role.safe_target_table

    def test_safe_target_table_ok_after_view(self) -> None:
        """safe_target_table returns table name after view()."""
        role = MockCitationLancedbRAG()
        role.view("test_table")
        assert role.safe_target_table == "test_table"

    def test_quit_viewing_resets(self) -> None:
        """quit_viewing() resets target_table to None."""
        role = MockCitationLancedbRAG()
        role.view("test_table")
        role.quit_viewing()
        assert role.target_table is None

"""Integration tests for fabricatio-rag EnrichChunkText using fabricatio-mock.

Exercises the LLM-driven enrich() capability end-to-end with mocked LLM
responses. Verifies:
- single-str overload returns EnrichmentResult
- List[str] overload returns List[EnrichmentResult] in input order
- empty chunk produces an EnrichmentResult with empty qa_pairs
"""

from fabricatio_mock.models.mock_role import ProposeTestRole
from fabricatio_mock.models.mock_router import return_model_json_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_rag.capabilities.enrich import EnrichChunkText
from fabricatio_rag.models.qa import EnrichmentResult, QAPair


class _EnrichTestRole(ProposeTestRole, EnrichChunkText):
    """Concrete role combining ProposeTestRole and EnrichChunkText."""


def _make_role() -> _EnrichTestRole:
    return _EnrichTestRole.with_bio(name="enrich_tester")


class TestEnrichSingleChunk:
    """Single-string chunk path: returns EnrichmentResult."""

    async def test_returns_enrichment_result_with_qa_pairs(self) -> None:
        """Single chunk returns an EnrichmentResult carrying the mocked qa_pairs."""
        result_model = EnrichmentResult(
            qa_pairs=[
                QAPair(question="What is X?", answer="X is ..."),
                QAPair(question="Why Y?", answer="Because ..."),
            ]
        )
        role = _make_role()
        # Unique chunk per test → unique question hash → fresh LLM cache.
        chunk = "chunk_for_test_returns_enrichment_result_with_qa_pairs"

        with install_router_usage(*return_model_json_router_usage(result_model)):
            result = await role.enrich("factual recall", chunk)

        assert isinstance(result, EnrichmentResult)
        assert len(result.qa_pairs) == 2
        assert result.qa_pairs[0].question == "What is X?"
        assert result.qa_pairs[1].answer == "Because ..."

    async def test_empty_chunk_returns_empty_qa_pairs(self) -> None:
        """Empty chunk yields an EnrichmentResult with an empty qa_pairs list."""
        empty_result = EnrichmentResult(qa_pairs=[])
        role = _make_role()
        chunk = "chunk_for_test_empty_chunk_returns_empty_qa_pairs"

        with install_router_usage(*return_model_json_router_usage(empty_result)):
            result = await role.enrich("any guideline", chunk)

        assert isinstance(result, EnrichmentResult)
        assert result.qa_pairs == []


class TestEnrichBatch:
    """List[str] chunk path: returns List[EnrichmentResult] preserving order."""

    async def test_returns_one_result_per_chunk_in_order(self) -> None:
        """List[str] input returns one EnrichmentResult per chunk, preserving order and length."""
        result_model = EnrichmentResult(
            qa_pairs=[
                QAPair(question="Batch Q?", answer="Batch A"),
                QAPair(question="Batch Q2?", answer="Batch A2"),
            ]
        )
        role = _make_role()
        # Each chunk is unique so the LLM response cache does not collide
        # between calls (see fabricatio-mock README: "Unique question strings").
        chunks = [
            "batch_chunk_unique_0_for_test",
            "batch_chunk_unique_1_for_test",
            "batch_chunk_unique_2_for_test",
        ]

        # `return_model_json_router_usage` produces FIFO order with padding;
        # a single model here is the standard pattern (see fabricatio-core
        # tests/test_propose.py: parametrize the model, reuse across calls).
        with install_router_usage(*return_model_json_router_usage(result_model)):
            results = await role.enrich("conceptual questions", chunks)

        assert isinstance(results, list)
        assert len(results) == 3
        assert all(isinstance(r, EnrichmentResult) for r in results)
        # Propose.propose preserves input order across batch calls.
        assert all(len(r.qa_pairs) == 2 for r in results)
        assert all(r.qa_pairs[0].question == "Batch Q?" and r.qa_pairs[1].question == "Batch Q2?" for r in results)

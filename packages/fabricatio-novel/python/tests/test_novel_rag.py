"""Tests for fabricatio-novel RAG capabilities, writing-style doc fetching, and reranking.

Focuses on:
- `GenerateChaptersFromScriptsWithRAG` builds the right fetch config and threads
  `writing_style_requirement` through to `create_chapters`.
- `NovelComposeRAG._fetch_style_docs` scales the fetch limit when a rerank
  target is provided and delegates to `arank_documents`.

Tests use `fabricatio_mock` for the LLM router and a lightweight in-process
`afetch_document` override on the test role so we do not need a live LanceDB.
"""

from typing import Any, Dict, List, Optional, Tuple

import pytest
from fabricatio_character.models.character import CharacterCard
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.capabilities.novel_rag import NovelComposeRAG
from fabricatio_novel.models.draft import ChapterDraft, NovelDraft
from fabricatio_novel.models.novel_rag import WritingStyleDocument, WritingStyleFetchConfig
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.scripting import Script
from pydantic import PrivateAttr


class _RAGTestRole(LLMTestRole, NovelComposeRAG):
    """Test role combining `LLMTestRole` with `NovelComposeRAG` for unit tests.

    The base `NovelComposeRAG` requires `LancedbRAG`'s `afetch_document`, which
    needs a real LanceDB connection. We override it here with an in-memory
    recorder so tests can assert on what was searched and ranked.
    """

    _fetched_queries: list = PrivateAttr(default_factory=list)
    _docs_by_query: dict = PrivateAttr(default_factory=dict)
    _ranked_queries: list = PrivateAttr(default_factory=list)

    def __init__(self, name: str = "rag-test") -> None:
        super().__init__(name=name)
        self._fetched_queries = []
        self._docs_by_query = {}
        self._ranked_queries = []

    @property
    def fetched_queries(self) -> List[Tuple[str, str, int]]:
        """Recorded afetch calls as (label, query, limit) tuples."""
        return self._fetched_queries

    @fetched_queries.setter
    def fetched_queries(self, value: List[Tuple[str, str, int]]) -> None:
        self._fetched_queries = value

    @property
    def docs_by_query(self) -> Dict[str, List[WritingStyleDocument]]:
        """Mapping of query -> returned docs."""
        return self._docs_by_query

    @docs_by_query.setter
    def docs_by_query(self, value: Dict[str, List[WritingStyleDocument]]) -> None:
        self._docs_by_query = value

    @property
    def ranked_queries(self) -> List[str]:
        """Recorded rerank query arguments (in invocation order)."""
        return self._ranked_queries

    @ranked_queries.setter
    def ranked_queries(self, value: List[str]) -> None:
        self._ranked_queries = value

    async def afetch_document(
        self,
        query: Any,
        config: Optional[WritingStyleFetchConfig] = None,
    ) -> List[WritingStyleDocument]:
        """Return pre-configured docs for each query, padded to conf.limit per query.

        Real LanceDB returns exactly conf.limit results per query in the flat
        concatenation. The test replicates each query's docs to fill its
        positional slot.
        """
        conf = config or WritingStyleFetchConfig.default()
        queries: List[str] = list(query) if isinstance(query, list) else [query]
        result: List[WritingStyleDocument] = []
        for q in queries:
            self._fetched_queries.append(("afetch", q, conf.limit))
            docs = list(self._docs_by_query.get(q, []))
            if docs:
                result.extend((docs * ((conf.limit // len(docs)) + 1))[: conf.limit])
        return result

    async def arefined_query(
        self,
        question: Any,
        send_to: str = "light",
        **kwargs: Any,
    ) -> List[str]:
        """Return the raw query text as a single-element list — no LLM refinement in tests."""
        raw = question if isinstance(question, str) else " ".join(question)
        return [raw]

    async def arank_documents(
        self,
        query: str,
        documents: List[WritingStyleDocument],
        **kwargs: Any,
    ) -> List[WritingStyleDocument]:
        """Record the rerank target and return docs in reverse (deterministic order)."""
        self._ranked_queries.append(query)
        return list(reversed(documents))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rag_role() -> _RAGTestRole:
    """Fresh `_RAGTestRole` per test."""
    return _RAGTestRole()


@pytest.fixture
def sample_draft() -> NovelDraft:
    """A single-chapter draft for RAG tests."""
    return NovelDraft(
        title="Test Novel",
        genre=["fantasy"],
        synopsis="A test synopsis.",
        character_descriptions=[],
        language="English",
        sketch="test",
        expected_word_count=3000,
        global_writing_constraint="",
        chapters=[
            ChapterDraft(
                title="Chapter 1",
                synopsis="The first chapter.",
                word_count=1000,
                weight=1.0,
            ),
        ],
    )


@pytest.fixture
def sample_character() -> CharacterCard:
    """A character for RAG tests."""
    return CharacterCard(
        name="Hero",
        role="Protagonist",
        look="Tall with brown hair.",
        act="Brave and kind.",
        want="Save the world.",
        flaw="Overconfident.",
        personality="Brave.",
    )


@pytest.fixture
def sample_script() -> Script:
    """A single-scene script for RAG tests."""
    return Script.with_raw_synosis("The hero begins the journey.")


def _make_doc(content: str) -> WritingStyleDocument:
    """Build a `WritingStyleDocument` for test fixtures."""
    return WritingStyleDocument(content=content)


def _fetch_query(original: str, rerank_query: Optional[str] = None) -> str:
    """Mirror the query-building logic from ``_fetch_style_docs`` for test key setup."""
    q = f"{original}\n\nNeed Some refined question to find QA docs related to the stuff above"
    if rerank_query:
        q += f"\nand below is the extra user constrain which is more prior to follow: \n{rerank_query}"
    return q


def _padded_responses() -> List[str]:
    """Build a padded response list for `install_router_usage`.

    Chapter generation consumes the first response, then `summarize_chapter`
    consumes the next. Pad with a parseable JSON default to keep the dummy
    model from running out of responses.
    """
    return return_router_usage(
        '"Generated chapter text."',
        default='{"key_events": [], "character_states": {}, "emotional_arc": "neutral.", "unresolved_threads": []}',
        padding=10,
    )


# ---------------------------------------------------------------------------
# 1. Config field tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 2. create_chapters wiring tests
# ---------------------------------------------------------------------------


class TestCreateChapters:
    """`create_chapters` fetches docs for scripts/scenes and optionally reranks."""

    @pytest.mark.asyncio
    async def test_fetches_docs_for_script_and_scenes(
        self,
        rag_role: _RAGTestRole,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """Without `writing_style_requirement`, fetches use script/scene prompts as queries."""
        script_query = sample_script.as_prompt()
        scene_query = sample_script.scenes[0].description
        rag_role.docs_by_query = {
            _fetch_query(script_query): [_make_doc("style-1")],
            _fetch_query(scene_query): [_make_doc("scene-1")],
        }
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        config = WritingStyleFetchConfig(limit=3)

        with install_router_usage(*_padded_responses()):
            await rag_role.create_chapters(
                sample_draft,
                chapter_plans,
                [sample_character],
                writing_style_fetch_config=config,
            )

        queries_used = [q for (_label, q, _limit) in rag_role.fetched_queries]
        assert any(script_query in q for q in queries_used)
        assert any(scene_query in q for q in queries_used)
        # No reranking without writing_style_requirement
        assert rag_role.ranked_queries == []

    @pytest.mark.asyncio
    async def test_reranks_when_requirement_provided(
        self,
        rag_role: _RAGTestRole,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """When `writing_style_requirement` is set, fetched docs are reranked against it."""
        script_query = sample_script.as_prompt()
        scene_query = sample_script.scenes[0].description
        requirement = "Hemingway terse prose"
        rag_role.docs_by_query = {
            _fetch_query(script_query, requirement): [_make_doc("style-1"), _make_doc("style-2")],
            _fetch_query(scene_query, requirement): [_make_doc("scene-1")],
        }
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        config = WritingStyleFetchConfig(limit=2)

        with install_router_usage(*_padded_responses()):
            await rag_role.create_chapters(
                sample_draft,
                chapter_plans,
                [sample_character],
                writing_style_fetch_config=config,
                writing_style_requirement="Hemingway terse prose",
            )

        # Both script and scene fetches should trigger rerank
        assert len(rag_role.ranked_queries) == 2
        assert all(rq == "Hemingway terse prose" for rq in rag_role.ranked_queries)

    @pytest.mark.asyncio
    async def test_fetch_limit_scaled_when_reranking(
        self,
        rag_role: _RAGTestRole,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """Rerank path fetches limit * rerank_scale_factor docs, then reranks to limit."""
        script_query = sample_script.as_prompt()
        scene_query = sample_script.scenes[0].description
        requirement = "test requirement"
        rag_role.docs_by_query = {
            _fetch_query(script_query, requirement): [_make_doc(f"d{i}") for i in range(10)],
            _fetch_query(scene_query, requirement): [_make_doc("s0")],
        }
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        config = WritingStyleFetchConfig(limit=3)

        with install_router_usage(*_padded_responses()):
            await rag_role.create_chapters(
                sample_draft,
                chapter_plans,
                [sample_character],
                writing_style_fetch_config=config,
                writing_style_requirement="test requirement",
            )

        # The fetch limit should be scaled: 3 * 3.0 = 9
        script_fetch = rag_role.fetched_queries[0]
        assert script_fetch[2] == 9  # limit field in recorded tuple

    @pytest.mark.asyncio
    async def test_whitespace_requirement_treated_as_empty(
        self,
        rag_role: _RAGTestRole,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """Whitespace-only `writing_style_requirement` skips reranking."""
        script_query = sample_script.as_prompt()
        scene_query = sample_script.scenes[0].description
        requirement = "   "
        rag_role.docs_by_query = {
            _fetch_query(script_query, requirement): [_make_doc("style-1")],
            _fetch_query(scene_query, requirement): [_make_doc("scene-1")],
        }
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        config = WritingStyleFetchConfig(limit=3)

        with install_router_usage(*_padded_responses()):
            await rag_role.create_chapters(
                sample_draft,
                chapter_plans,
                [sample_character],
                writing_style_fetch_config=config,
                writing_style_requirement="   ",
            )

        # Reranking should be skipped for whitespace-only requirement
        assert rag_role.ranked_queries == []


# ---------------------------------------------------------------------------
# 3. Action-level config wiring
# ---------------------------------------------------------------------------


class TestGenerateChaptersFromScriptsWithRAGConfig:
    """`GenerateChaptersFromScriptsWithRAG` exposes the new field correctly."""

    def test_action_exposes_writing_style_requirement(self) -> None:
        """The action class declares `writing_style_requirement` with proper type."""
        from fabricatio_novel.actions.novel_rag import GenerateChaptersFromScriptsWithRAG

        action = GenerateChaptersFromScriptsWithRAG(
            novel_draft=NovelDraft.model_construct(  # type: ignore[call-arg]
                title="x",
                genre=[],
                synopsis="",
                character_descriptions=[],
                chapters=[],
                expected_word_count=0,
                language="en",
                sketch="",
            ),
            novel_scripts=[],
            novel_characters=[],
            writing_style_requirement="Hemingway terse prose",
        )
        assert action.writing_style_requirement == "Hemingway terse prose"

    def test_action_orphan_actions_removed(self) -> None:
        """`RetrieveWritingStyles` and `InjectWritingStyleToScript` were dead code — removed."""
        from fabricatio_novel.actions import novel_rag

        for name in ("RetrieveWritingStyles", "InjectWritingStyleToScript"):
            assert not hasattr(novel_rag, name), f"{name} should be removed"

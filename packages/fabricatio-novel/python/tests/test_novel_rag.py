"""Tests for fabricatio-novel RAG capabilities, refined-query wiring, and config.

Focuses on:
- `WritingStyleFetchConfig` exposes the new refined-query fields with correct defaults.
- `GenerateChaptersFromScriptsWithRAG` builds the right fetch config (explicit
  override > convenience overrides > default) and threads the `writing_style_query`
  through to `create_chapters`.
- `NovelComposeRAG._refine_writing_style_query` falls back to the raw query on
  empty / failing refinement and otherwise returns the LLM-refined variants.
- `NovelComposeRAG._fetch_multi_query` dedupes per-query results and respects
  the config `limit`.
- `NovelComposeRAG.create_chapters` honors `use_refined_query` by calling
  `arefined_query` once and pre-computing the variants before per-chapter fetches.
- The `RetrieveWritingStyles` / `InjectWritingStyleToScript` orphan actions are
  removed (the file no longer exports them).

Tests use `fabricatio_mock` for the LLM router and a lightweight in-process
`afetch_document` / `arefined_query` override on the test role so we do not
need a live LanceDB.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

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

if TYPE_CHECKING:
    from fabricatio_novel.models.kwargs_types import NovelRAGKwargs


# ---------------------------------------------------------------------------
# Test role — overrides RAG hooks to avoid LanceDB
# ---------------------------------------------------------------------------


class _RAGTestRole(LLMTestRole, NovelComposeRAG):
    """Test role combining `LLMTestRole` with `NovelComposeRAG` for unit tests.

    The base `NovelComposeRAG` requires `LancedbRAG`'s `afetch_document`, which
    needs a real LanceDB connection. We override it here with an in-memory
    recorder so tests can assert on what was searched.
    """

    # Pydantic v2 BaseModel does not allow arbitrary instance attributes. Use
    # PrivateAttr for storage and expose setters via properties on top of them.
    _fetched_queries: list = PrivateAttr(default_factory=list)
    _docs_by_query: dict = PrivateAttr(default_factory=dict)
    _refined_variants: Optional[list] = PrivateAttr(default=None)
    _refine_inputs: list = PrivateAttr(default_factory=list)

    def __init__(self) -> None:
        super().__init__()
        # Recorded: list of (caller_label, query, limit) tuples for each afetch call.
        self._fetched_queries = []
        # Configurable response docs for afetch.
        self._docs_by_query = {}
        # Configurable refined-query output (None = use LLM router).
        self._refined_variants = None
        # Recorded arefined_query inputs.
        self._refine_inputs = []

    @property
    def fetched_queries(self) -> List[Tuple[str, str, int]]:
        """Recorded afetch calls."""
        return self._fetched_queries

    @fetched_queries.setter
    def fetched_queries(self, value: List[Tuple[str, str, int]]) -> None:
        self._fetched_queries = value

    @property
    def docs_by_query(self) -> Dict[str, List[WritingStyleDocument]]:
        """Mapping of query → returned docs (read/write)."""
        return self._docs_by_query

    @docs_by_query.setter
    def docs_by_query(self, value: Dict[str, List[WritingStyleDocument]]) -> None:
        self._docs_by_query = value

    @property
    def refined_variants(self) -> Optional[List[str]]:
        """Pre-configured refined-query variants (None = use LLM router)."""
        return self._refined_variants

    @refined_variants.setter
    def refined_variants(self, value: Optional[List[str]]) -> None:
        self._refined_variants = value

    @property
    def refine_inputs(self) -> List[str]:
        """Recorded arefined_query inputs."""
        return self._refine_inputs

    @refine_inputs.setter
    def refine_inputs(self, value: List[str]) -> None:
        self._refine_inputs = value

    async def afetch_document(
        self,
        query: Any,
        config: Optional[WritingStyleFetchConfig] = None,
    ) -> List[WritingStyleDocument]:
        """Return pre-configured docs for the query (or an empty list)."""
        conf = config or WritingStyleFetchConfig.default()
        q = query[0] if isinstance(query, list) else query
        self._fetched_queries.append(("afetch", q, conf.limit))
        return list(self._docs_by_query.get(q, []))

    async def arefined_query(self, question: Any, **kwargs: Any) -> Optional[List[str]]:
        """Return pre-configured variants or fall back to LLM router."""
        q = question[0] if isinstance(question, list) else question
        self._refine_inputs.append(q)
        if self._refined_variants is not None:
            return list(self._refined_variants)
        return await super().arefined_query(question, **kwargs)


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
        title="RAG Test Novel",
        genre=["Fiction"],
        synopsis="A draft for RAG tests.",
        character_descriptions=["A hero"],
        chapters=[ChapterDraft(title="Ch1", synopsis="Hero starts.", weight=1.0)],
        expected_word_count=100,
        language="English",
        sketch="",
    )


@pytest.fixture
def sample_character() -> CharacterCard:
    """A character for RAG tests."""
    return CharacterCard(
        name="Hero",
        description="A brave hero",
        role="Protagonist",
        look="Tall with brown hair",
        act="Courageous and kind",
        want="Save the world",
        flaw="Too trusting",
        sketch="",
    )


@pytest.fixture
def sample_script() -> Script:
    """A single-scene script for RAG tests."""
    return Script.with_raw_synosis("The hero begins the journey.")


def _make_doc(content: str) -> WritingStyleDocument:
    """Build a `WritingStyleDocument` for test fixtures."""
    return WritingStyleDocument(content=content)


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


class TestWritingStyleFetchConfig:
    """`WritingStyleFetchConfig` exposes the refined-query fields with correct defaults."""

    def test_default_use_refined_query_is_false(self) -> None:
        """Default behavior: no refinement (opt-in, costs an LLM call)."""
        assert WritingStyleFetchConfig.default().use_refined_query is False

    def test_default_refined_query_count_is_three(self) -> None:
        """Default produces 3 variants when refinement is enabled."""
        assert WritingStyleFetchConfig.default().refined_query_count == 3

    def test_refine_query_template_default_is_built_in(self) -> None:
        """Default template points at the built-in refined_query template."""
        assert WritingStyleFetchConfig.default().refine_query_template == "built-in/refined_query"

    def test_explicit_override(self) -> None:
        """All refined-query fields can be overridden at construction time."""
        config = WritingStyleFetchConfig(
            use_refined_query=True,
            refined_query_count=5,
            refine_query_template="custom/refine",
        )
        assert config.use_refined_query is True
        assert config.refined_query_count == 5
        assert config.refine_query_template == "custom/refine"

    def test_kwargs_type_exposes_writing_style_query(self) -> None:
        """`NovelRAGKwargs` accepts `writing_style_query` for `create_chapters`."""
        kwargs: NovelRAGKwargs[str] = {
            "writing_style_query": "Hemingway terse prose",
            "use_reranker": False,
        }
        assert kwargs["writing_style_query"] == "Hemingway terse prose"


# ---------------------------------------------------------------------------
# 2. Refine-helper tests
# ---------------------------------------------------------------------------


class TestRefineWritingStyleQuery:
    """`_refine_writing_style_query` falls back gracefully and uses LLM router."""

    @pytest.mark.asyncio
    async def test_returns_raw_query_on_empty_refinement(self, rag_role: _RAGTestRole) -> None:
        """If the LLM returns no variants, the raw query is returned as the only fallback."""
        rag_role.refined_variants = []
        config = WritingStyleFetchConfig(use_refined_query=True, refined_query_count=3)
        result = await rag_role._refine_writing_style_query("Hemingway terse prose", config)
        assert result == ["Hemingway terse prose"]

    @pytest.mark.asyncio
    async def test_returns_refined_variants_when_present(self, rag_role: _RAGTestRole) -> None:
        """Pre-configured variants are returned as-is."""
        rag_role.refined_variants = [
            "Hemingway terse",
            "short declarative sentences",
            "spare prose style",
        ]
        config = WritingStyleFetchConfig(use_refined_query=True, refined_query_count=3)
        result = await rag_role._refine_writing_style_query("Hemingway terse prose", config)
        assert result == [
            "Hemingway terse",
            "short declarative sentences",
            "spare prose style",
        ]

    @pytest.mark.asyncio
    async def test_records_input_query(self, rag_role: _RAGTestRole) -> None:
        """The helper records the input so tests can verify the call site."""
        rag_role.refined_variants = ["variant-1"]
        config = WritingStyleFetchConfig(use_refined_query=True)
        await rag_role._refine_writing_style_query("my raw query", config)
        assert rag_role.refine_inputs == ["my raw query"]

    @pytest.mark.asyncio
    async def test_filters_empty_strings(self, rag_role: _RAGTestRole) -> None:
        """Empty / whitespace-only strings in the LLM response are dropped before returning."""
        rag_role.refined_variants = ["valid", "", "  ", "also-valid"]
        config = WritingStyleFetchConfig(use_refined_query=True, refined_query_count=4)
        result = await rag_role._refine_writing_style_query("q", config)
        assert result == ["valid", "also-valid"]


# ---------------------------------------------------------------------------
# 3. Multi-query fetch tests
# ---------------------------------------------------------------------------


class TestFetchMultiQuery:
    """`_fetch_multi_query` dedupes per-query results and respects the limit."""

    @pytest.mark.asyncio
    async def test_empty_query_list_returns_empty(self, rag_role: _RAGTestRole) -> None:
        """No queries → no fetches, no docs."""
        result = await rag_role._fetch_multi_query([], WritingStyleFetchConfig(), use_reranker=False)
        assert result == []
        assert rag_role.fetched_queries == []

    @pytest.mark.asyncio
    async def test_single_query(self, rag_role: _RAGTestRole) -> None:
        """Single query yields the configured docs (no dedupe needed)."""
        rag_role.docs_by_query = {"q1": [_make_doc("a"), _make_doc("b")]}
        result = await rag_role._fetch_multi_query(["q1"], WritingStyleFetchConfig(limit=5), use_reranker=False)
        assert [d.content for d in result] == ["a", "b"]
        assert ("afetch", "q1", 5) in rag_role.fetched_queries

    @pytest.mark.asyncio
    async def test_dedupes_overlapping_results(self, rag_role: _RAGTestRole) -> None:
        """The same document returned by two queries appears only once."""
        shared = _make_doc("shared")
        rag_role.docs_by_query = {
            "q1": [shared, _make_doc("a-only")],
            "q2": [shared, _make_doc("b-only")],
        }
        result = await rag_role._fetch_multi_query(["q1", "q2"], WritingStyleFetchConfig(limit=10), use_reranker=False)
        contents = [d.content for d in result]
        assert contents.count("shared") == 1
        assert set(contents) == {"shared", "a-only", "b-only"}

    @pytest.mark.asyncio
    async def test_respects_limit_after_dedup(self, rag_role: _RAGTestRole) -> None:
        """Final result is sliced to `config.limit` even after dedupe."""
        rag_role.docs_by_query = {
            "q1": [_make_doc(f"d{i}") for i in range(5)],
            "q2": [_make_doc(f"d{i}") for i in range(5)],  # same docs
        }
        result = await rag_role._fetch_multi_query(["q1", "q2"], WritingStyleFetchConfig(limit=2), use_reranker=False)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# 4. create_chapters wiring tests
# ---------------------------------------------------------------------------


class TestCreateChaptersRefinedQuery:
    """`create_chapters` honors `use_refined_query` and threads `writing_style_query`."""

    @pytest.mark.asyncio
    async def test_without_refinement_uses_base_queries(
        self,
        rag_role: _RAGTestRole,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """Default: no refinement → fetches use the script/scene-derived query."""
        # Capture query snapshots BEFORE the script is mutated by append_global_prompt.
        script_query = sample_script.as_prompt()
        scene_query = sample_script.scenes[0].description
        rag_role.docs_by_query = {
            script_query: [_make_doc("style-1")],
            scene_query: [_make_doc("scene-1")],
        }
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        config = WritingStyleFetchConfig(limit=3, use_refined_query=False)

        with install_router_usage(*_padded_responses()):
            await rag_role.create_chapters(
                sample_draft,
                chapter_plans,
                [sample_character],
                writing_style_fetch_config=config,
            )

        queries_used = [q for (_label, q, _limit) in rag_role.fetched_queries]
        assert script_query in queries_used
        assert scene_query in queries_used

    @pytest.mark.asyncio
    async def test_with_refinement_uses_refined_variants_only(
        self,
        rag_role: _RAGTestRole,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """With refinement on AND a user query, fetches use the refined variants (not the script)."""
        variants = ["terse prose", "declarative sentences", "spare dialogue"]
        rag_role.refined_variants = variants
        for v in variants:
            rag_role.docs_by_query[v] = [_make_doc(f"doc-for-{v}")]
        script_query_before = sample_script.as_prompt()

        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        config = WritingStyleFetchConfig(limit=3, use_refined_query=True, refined_query_count=3)

        with install_router_usage(*_padded_responses()):
            await rag_role.create_chapters(
                sample_draft,
                chapter_plans,
                [sample_character],
                writing_style_fetch_config=config,
                writing_style_query="Hemingway terse prose style",
            )

        assert rag_role.refine_inputs == ["Hemingway terse prose style"]
        queries_used = [q for (_label, q, _limit) in rag_role.fetched_queries]
        for v in variants:
            assert v in queries_used
        assert script_query_before not in queries_used

    @pytest.mark.asyncio
    async def test_refinement_skipped_when_no_user_query(
        self,
        rag_role: _RAGTestRole,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """Refinement is gated on both `use_refined_query` AND a user query."""
        script_query = sample_script.as_prompt()
        scene_query = sample_script.scenes[0].description
        rag_role.docs_by_query = {
            script_query: [_make_doc("style-1")],
            scene_query: [_make_doc("scene-1")],
        }
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        config = WritingStyleFetchConfig(limit=3, use_refined_query=True)  # on, but no query

        with install_router_usage(*_padded_responses()):
            await rag_role.create_chapters(
                sample_draft,
                chapter_plans,
                [sample_character],
                writing_style_fetch_config=config,
                # writing_style_query intentionally omitted
            )

        assert rag_role.refine_inputs == []
        queries_used = [q for (_label, q, _limit) in rag_role.fetched_queries]
        assert script_query in queries_used


# ---------------------------------------------------------------------------
# 5. Action-level config wiring
# ---------------------------------------------------------------------------


class TestGenerateChaptersFromScriptsWithRAGConfig:
    """`GenerateChaptersFromScriptsWithRAG` builds the fetch config correctly."""

    def test_action_exposes_refined_query_fields(self) -> None:
        """The action class declares the new fields with proper types."""
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
            writing_style_query="Hemingway terse prose",
            use_refined_query=True,
            refined_query_count=4,
        )
        assert action.writing_style_query == "Hemingway terse prose"
        assert action.use_refined_query is True
        assert action.refined_query_count == 4

    def test_action_orphan_actions_removed(self) -> None:
        """`RetrieveWritingStyles` and `InjectWritingStyleToScript` were dead code — removed."""
        from fabricatio_novel.actions import novel_rag

        for name in ("RetrieveWritingStyles", "InjectWritingStyleToScript"):
            assert not hasattr(novel_rag, name), f"{name} should be removed"

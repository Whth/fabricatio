"""Tests for the combined RAG + state consistency capability (NovelComposeStateRAG).

Focuses on:
- ``StateRAGChapterContext`` / ``NovelComposeStateRAG`` compose both mixins on
  one channel: state board + injected style docs in the same rendered prompt.
- The full ``create_chapters`` loop audits state (committing histories) while
  injecting style docs per chapter; regeneration re-runs both paths.
- The actions mirror the state / mental+RAG action shapes.

Tests use ``fabricatio_mock`` for the LLM router and in-memory
``afetch_document`` / ``arefined_query`` / ``arank_documents`` overrides on
the test role so no live LanceDB or LLM refinement is needed.
"""

from typing import Any, Dict, List, Optional

import pytest
from fabricatio_character.models.character import CharacterCard
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_model_json_router_usage, return_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.capabilities.novel_rag import RAGChapterContext
from fabricatio_novel.capabilities.novel_state import StateChapterContext
from fabricatio_novel.capabilities.novel_state_rag import NovelComposeStateRAG, StateRAGChapterContext
from fabricatio_novel.models.chapter_state import ChapterStateRecord, CharacterState
from fabricatio_novel.models.draft import ChapterDraft, NovelDraft
from fabricatio_novel.models.novel_rag import WritingStyleDocument, WritingStyleFetchConfig
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.scripting import Script
from pydantic import PrivateAttr

CHAPTER_TEXT = "P0: The hero stood by the window.\n\nP1: The hero walked to the door."


@pytest.fixture
def sample_draft() -> NovelDraft:
    """A single-chapter draft for state+RAG tests."""
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
    """A character for state+RAG tests."""
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
    """A single-scene script for state+RAG tests."""
    return Script.with_raw_synosis("The hero begins the journey.")


def _make_doc(content: str) -> WritingStyleDocument:
    """Build a WritingStyleDocument for test fixtures."""
    return WritingStyleDocument(content=content)


def _fetch_query(original: str) -> str:
    """Mirror the query-building logic from ``_fetch_style_docs`` (no rerank)."""
    return f"{original}\n\nNeed Some refined question to find QA docs related to the stuff above"


def _padded_doc_responses() -> List[str]:
    """Padded responses so any LLM call inside the RAG prepare path succeeds."""
    return return_model_json_router_usage(
        _make_doc("style-default"),
        default=WritingStyleDocument(content="default").model_dump_json(),
    )


class _StateRAGTestRole(LLMTestRole, NovelComposeStateRAG):
    """Test role combining `LLMTestRole` with `NovelComposeStateRAG`.

    The base `NovelComposeRAG` requires `LancedbRAG`'s `afetch_document`,
    which needs a real LanceDB connection — overridden with an in-memory
    mapping so tests assert on what was searched, ranked, and injected.
    """

    _docs_by_query: Dict[str, List[WritingStyleDocument]] = PrivateAttr(default_factory=dict)
    _ranked_queries: List[str] = PrivateAttr(default_factory=list)
    _extraction_raws: List[str] = PrivateAttr(default_factory=list)

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
        """Return pre-configured docs for each query, padded to conf.limit per query."""
        conf = config or WritingStyleFetchConfig.default()
        queries: List[str] = list(query) if isinstance(query, list) else [query]
        result: List[WritingStyleDocument] = []
        for q in queries:
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

    async def _extract_state_record(self, ctx: StateChapterContext, raw: str) -> Optional[ChapterStateRecord]:
        """Record every extraction input (asserts the gate saw the prose)."""
        self._extraction_raws.append(raw)
        return await super()._extract_state_record(ctx, raw)


class TestCombinedCapability:
    """The combined channel and capability compose both mixins."""

    def test_context_isa_both_and_builds(self) -> None:
        """StateRAGChapterContext is both channels; build_chapter_context returns it."""
        assert issubclass(StateRAGChapterContext, StateChapterContext)
        assert issubclass(StateRAGChapterContext, RAGChapterContext)
        ctx = StateRAGChapterContext(writing_style_fetch_config=WritingStyleFetchConfig(limit=2))
        assert isinstance(ctx, StateChapterContext)
        assert isinstance(ctx, RAGChapterContext)
        assert ctx.writing_style_fetch_config is not None
        assert ctx.writing_style_fetch_config.limit == 2

    @pytest.mark.asyncio
    async def test_build_chapter_context_returns_combined(self, sample_character: CharacterCard) -> None:
        """compose_novel's seam builds the combined channel without seeding."""
        role = _StateRAGTestRole(name="novel-state-rag-build")
        ctx = await role.build_chapter_context([sample_character])
        assert isinstance(ctx, StateRAGChapterContext)
        assert ctx.character_state_histories == {}
        assert ctx.characters is None


class TestPromptComposition:
    """State board + injected style docs land in the same rendered prompt."""

    @pytest.mark.asyncio
    async def test_prepare_renders_board_and_style_docs(
        self,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """The rendered prompt carries the state board AND the fetched style docs."""
        role = _StateRAGTestRole(name="novel-state-rag-prepare")
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        plan = chapter_plans[0]
        role.docs_by_query = {
            _fetch_query(plan.script.as_prompt()): [_make_doc("style-1")],
            _fetch_query(plan.script.scenes[0].description): [_make_doc("scene-1")],
        }
        ctx = (
            StateRAGChapterContext(writing_style_fetch_config=WritingStyleFetchConfig(limit=3))
            .set_draft(sample_draft)
            .set_chapter_plans(chapter_plans)
            .set_characters([sample_character])
        )
        ctx.record_chapter_states(
            ChapterStateRecord(
                characters=[
                    CharacterState(character="Hero", states=["standing"], paragraphs=[0], chapter_end_state="standing")
                ]
            )
        )
        with install_router_usage(*_padded_doc_responses()):
            rendered = await role.prepare_chapter_prompt(ctx)

        assert "style-1" in plan.script.global_prompt
        assert "scene-1" in plan.script.scenes[0].prompt
        assert "Character State Board" in rendered
        assert "Hero: standing (end of chapter 0)" in rendered
        assert set(ctx.chapter_prompt_vars) == {"character_state_board"}
        assert role.ranked_queries == []


class TestFullLoop:
    """create_chapters runs the audit gate AND injects style docs per chapter."""

    @pytest.mark.asyncio
    async def test_create_chapters_audits_and_injects(
        self,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """A clean chapter commits its end state while style docs reach the plan."""
        role = _StateRAGTestRole(name="novel-state-rag-loop")
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        plan = chapter_plans[0]
        role.docs_by_query = {
            _fetch_query(plan.script.as_prompt()): [_make_doc("style-1")],
            _fetch_query(plan.script.scenes[0].description): [_make_doc("scene-1")],
        }
        record = ChapterStateRecord(
            characters=[
                CharacterState(
                    character="Hero",
                    states=["standing by the window", "walking to the door"],
                    paragraphs=[0, 1],
                    chapter_end_state="walking to the door",
                )
            ],
            violations=[],
        )
        summary_json = (
            '{"key_events": [], "character_states": {}, "emotional_arc": "neutral.", "unresolved_threads": []}'
        )
        # Flat queue: chapter aask, state propose, summary propose; parseable padding after.
        responses = return_router_usage(
            CHAPTER_TEXT,
            record.model_dump_json(),
            summary_json,
            default=ChapterStateRecord().model_dump_json(),
        )
        ctx = StateRAGChapterContext(writing_style_fetch_config=WritingStyleFetchConfig(limit=3))
        with install_router_usage(*responses):
            chapter_contents = await role.create_chapters(
                sample_draft,
                chapter_plans,
                [sample_character],
                context=ctx,
            )

        assert chapter_contents == [CHAPTER_TEXT]
        assert ctx.character_state_histories == {"Hero": [(0, "walking to the door")]}
        assert ctx.character_in_chapter_states == {"Hero": ["standing by the window", "walking to the door"]}
        assert ctx.state_violations == []
        assert role._extraction_raws == [CHAPTER_TEXT]
        assert "style-1" in plan.script.global_prompt
        assert role.ranked_queries == []

    @pytest.mark.asyncio
    async def test_create_chapters_regenerates_once_on_violations(
        self,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """A violation triggers one rewrite; histories come from the FINAL text's record."""
        role = _StateRAGTestRole(name="novel-state-rag-regen")
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        plan = chapter_plans[0]
        role.docs_by_query = {
            _fetch_query(plan.script.as_prompt()): [_make_doc("style-1")],
            _fetch_query(plan.script.scenes[0].description): [_make_doc("scene-1")],
        }
        rejected = ChapterStateRecord(
            characters=[
                CharacterState(
                    character="Hero",
                    states=["standing by the window", "standing at the door"],
                    paragraphs=[0, 1],
                    chapter_end_state="standing at the door",
                )
            ],
            violations=["Hero: paragraph 1 at the door with no described motion"],
        )
        clean = ChapterStateRecord(
            characters=[
                CharacterState(
                    character="Hero",
                    states=["standing by the window", "walking to the door", "standing at the door"],
                    paragraphs=[0, 1, 1],
                    chapter_end_state="standing at the door",
                )
            ],
            violations=[],
        )
        rewritten = "P0: The hero stood by the window.\n\nP1: The hero walked to the door and stood there."
        summary_json = (
            '{"key_events": [], "character_states": {}, "emotional_arc": "neutral.", "unresolved_threads": []}'
        )
        # Flat queue: chapter aask, propose #1 (rejected), regen aask, propose #2 (clean), summary propose.
        responses = return_router_usage(
            CHAPTER_TEXT,
            rejected.model_dump_json(),
            rewritten,
            clean.model_dump_json(),
            summary_json,
            default=ChapterStateRecord().model_dump_json(),
        )
        ctx = StateRAGChapterContext(writing_style_fetch_config=WritingStyleFetchConfig(limit=3))
        with install_router_usage(*responses):
            chapter_contents = await role.create_chapters(
                sample_draft,
                chapter_plans,
                [sample_character],
                context=ctx,
            )

        assert chapter_contents == [rewritten]
        assert role._extraction_raws == [CHAPTER_TEXT, rewritten]
        assert ctx.character_state_histories == {"Hero": [(0, "standing at the door")]}
        assert ctx.state_violations == ["Hero: paragraph 1 at the door with no described motion"]
        assert "style-1" in plan.script.global_prompt


class TestStateRAGActions:
    """Combined action classes shape and MRO."""

    def test_actions_inherit_capability_and_action(self) -> None:
        """`GenerateNovelStateRAG` / `GenerateChaptersFromScriptsWithStateRAG` inherit capability + `Action`."""
        from fabricatio_core.models.action import Action
        from fabricatio_novel.actions.novel_state_rag import (
            GenerateChaptersFromScriptsWithStateRAG,
            GenerateNovelStateRAG,
        )

        assert issubclass(GenerateNovelStateRAG, NovelComposeStateRAG)
        assert issubclass(GenerateNovelStateRAG, Action)
        assert issubclass(GenerateChaptersFromScriptsWithStateRAG, NovelComposeStateRAG)
        assert issubclass(GenerateChaptersFromScriptsWithStateRAG, Action)

    def test_actions_have_ctx_override_true(self) -> None:
        """Both actions follow project convention `ctx_override=True`."""
        from fabricatio_novel.actions.novel_state_rag import (
            GenerateChaptersFromScriptsWithStateRAG,
            GenerateNovelStateRAG,
        )

        assert GenerateNovelStateRAG.ctx_override is True
        assert GenerateChaptersFromScriptsWithStateRAG.ctx_override is True

    def test_actions_expose_output_keys(self) -> None:
        """`output_key` defaults mirror the state/mental actions (`novel` / `novel_chapter_contents`)."""
        from fabricatio_novel.actions.novel_state_rag import (
            GenerateChaptersFromScriptsWithStateRAG,
            GenerateNovelStateRAG,
        )

        assert GenerateNovelStateRAG.model_fields["output_key"].default == "novel"
        assert GenerateChaptersFromScriptsWithStateRAG.model_fields["output_key"].default == "novel_chapter_contents"

    def test_chapter_action_exposes_rag_fields(self) -> None:
        """The chapter action threads the RAG fetch config and rerank target."""
        from fabricatio_novel.actions.novel_state_rag import GenerateChaptersFromScriptsWithStateRAG

        assert "writing_style_fetch_config" in GenerateChaptersFromScriptsWithStateRAG.model_fields
        assert "writing_style_requirement" in GenerateChaptersFromScriptsWithStateRAG.model_fields

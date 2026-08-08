"""Tests for fabricatio-novel character state consistency (base seam + NovelComposeState)."""

from typing import Any, Dict, List, Optional

import pytest
from fabricatio_character.models.character import CharacterCard
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_model_json_router_usage, return_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.capabilities.novel_mental import MentalChapterContext, NovelComposeMental
from fabricatio_novel.capabilities.novel_rag import NovelComposeRAG, RAGChapterContext
from fabricatio_novel.capabilities.novel_state import NovelComposeState, StateChapterContext
from fabricatio_novel.models.chapter_context import ChapterContext
from fabricatio_novel.models.chapter_state import ChapterStateRecord, CharacterState
from fabricatio_novel.models.draft import ChapterDraft, NovelDraft
from fabricatio_novel.models.novel_rag import WritingStyleDocument, WritingStyleFetchConfig
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.scripting import ChapterSummary, Script
from pydantic import PrivateAttr

CHAPTER_TEXT = "P0: The hero stood by the window.\n\nP1: The hero walked to the door."


@pytest.fixture
def sample_draft() -> NovelDraft:
    """A single-chapter draft for state tests."""
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
    """A character for state tests."""
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
    """A single-scene script for state tests."""
    return Script.with_raw_synosis("The hero begins the journey.")


class _RecordingRole(LLMTestRole, NovelCompose):
    """Records hook timing to assert the loop invariant and pending staging."""

    _hook_indexes: Dict[str, int] = PrivateAttr(default_factory=dict)
    _pending_at_hook: Dict[str, Optional[str]] = PrivateAttr(default_factory=dict)
    _current_summary_ok: bool = PrivateAttr(default=False)

    async def prepare_chapter_prompt(self, ctx: ChapterContext) -> str:
        self._hook_indexes["prepare"] = ctx.chapter_index()
        self._pending_at_hook["prepare"] = ctx.pending_chapter()
        return await super().prepare_chapter_prompt(ctx)

    async def after_chapter_gen(self, ctx: ChapterContext) -> None:
        self._hook_indexes["after_gen"] = ctx.chapter_index()
        self._pending_at_hook["after_gen"] = ctx.pending_chapter()
        return await super().after_chapter_gen(ctx)

    async def after_chapter_summarize(self, ctx: ChapterContext) -> None:
        self._hook_indexes["after_summarize"] = ctx.chapter_index()
        self._pending_at_hook["after_summarize"] = ctx.pending_chapter()
        self._current_summary_ok = ctx.current_summary() is not None
        return await super().after_chapter_summarize(ctx)


class TestChapterStateModels:
    """The extraction models validate and round-trip through JSON."""

    def test_record_roundtrip_validation(self) -> None:
        """A ChapterStateRecord validates, keeps anchors aligned, and survives JSON round-trip."""
        from fabricatio_novel.models.chapter_state import ChapterStateRecord, CharacterState

        record = ChapterStateRecord(
            characters=[
                CharacterState(
                    character="Hero",
                    states=["standing by the window", "seated"],
                    paragraphs=[0, 3],
                    chapter_end_state="seated",
                )
            ],
            violations=["Hero: paragraph 3 seated with no described motion"],
        )
        assert record.characters[0].chapter_end_state == "seated"
        assert len(record.characters[0].paragraphs) == len(record.characters[0].states)
        restored = ChapterStateRecord.model_validate_json(record.model_dump_json())
        assert restored == record


class TestMentalCooperativeMerge:
    """Mental's extra vars land on the channel unchanged when it is the sole override."""

    @pytest.mark.asyncio
    async def test_sole_override_output_preserved(self, sample_character: CharacterCard) -> None:
        """A sole mental override still contributes exactly its own board vars."""
        from fabricatio_character.models.mental import MentalState
        from fabricatio_novel.capabilities.novel_mental import MentalChapterContext, NovelComposeMental

        class _MentalRole(LLMTestRole, NovelComposeMental):
            pass

        role = _MentalRole(name="mental-merge-regression")
        ctx = MentalChapterContext(character_states={sample_character.name: MentalState.from_card(sample_character)})
        assert role.extra_chapter_prompt_vars(ctx) is None
        assert set(ctx.chapter_prompt_vars) == {"character_mental_states"}
        assert "Hero" in ctx.chapter_prompt_vars["character_mental_states"]


class TestPromptVarsChannel:
    """chapter_prompt_vars is channel state mutated via chainable writers."""

    def test_add_and_reset_prompt_vars(self) -> None:
        """add_prompt_vars merges and chains; reset_prompt_vars clears for the next render."""
        ctx = ChapterContext()
        assert ctx.add_prompt_vars({"a": "1"}).add_prompt_vars({"b": "2"}) is ctx
        assert ctx.chapter_prompt_vars == {"a": "1", "b": "2"}
        ctx.reset_prompt_vars()
        assert ctx.chapter_prompt_vars == {}

    @pytest.mark.asyncio
    async def test_prepare_resets_vars_every_render(
        self,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """A later render never sees prompt vars contributed by an earlier render."""

        class _OnceRole(LLMTestRole, NovelCompose):
            """Adds a prompt var only on the first hook call."""

            _once_var_added: bool = PrivateAttr(default=False)

            def extra_chapter_prompt_vars(self, ctx: ChapterContext) -> None:
                if not self._once_var_added:
                    self._once_var_added = True
                    ctx.add_prompt_vars({"once": "1"})

        role = _OnceRole(name="novel-prompt-reset")
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        ctx = (
            ChapterContext().set_draft(sample_draft).set_chapter_plans(chapter_plans).set_characters([sample_character])
        )
        await role.prepare_chapter_prompt(ctx)
        assert ctx.chapter_prompt_vars == {"once": "1"}
        await role.prepare_chapter_prompt(ctx)
        assert ctx.chapter_prompt_vars == {}


class _StateTestRole(LLMTestRole, NovelComposeState):
    """Test role combining LLMTestRole with NovelComposeState."""

    _extraction_raws: List[str] = PrivateAttr(default_factory=list)

    async def _extract_state_record(self, ctx: StateChapterContext, raw: str) -> Optional[ChapterStateRecord]:
        self._extraction_raws.append(raw)
        return await super()._extract_state_record(ctx, raw)


class TestStateChannelHook:
    """The state gate runs over the caller-owned channel via after_chapter_gen."""

    @pytest.mark.asyncio
    async def test_clean_extraction_commits_to_channel(
        self,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """A clean record commits end states to history, local sequences, and no violations."""
        role = _StateTestRole(name="novel-state-hook")
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
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
        ctx = (
            StateChapterContext()
            .set_draft(sample_draft)
            .set_chapter_plans(chapter_plans)
            .set_characters([sample_character])
            .set_pending_chapter(0, CHAPTER_TEXT)
        )
        with install_router_usage(*return_model_json_router_usage(record)):
            await role.after_chapter_gen(ctx)

        assert ctx.state_ledger.histories == {"Hero": [(0, "walking to the door")]}
        assert ctx.state_ledger.violations == []
        assert role._extraction_raws == [CHAPTER_TEXT]

    @pytest.mark.asyncio
    async def test_skips_without_state_context(
        self,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """A plain channel means the gate delegates without extracting or mutating."""
        role = _StateTestRole(name="novel-state-skip")
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        ctx = (
            ChapterContext()
            .set_draft(sample_draft)
            .set_chapter_plans(chapter_plans)
            .set_characters([sample_character])
            .set_pending_chapter(0, CHAPTER_TEXT)
        )
        # No router responses installed: any LLM call would fail — the gate must not run.
        await role.after_chapter_gen(ctx)
        assert role._extraction_raws == []
        assert ctx.pending_chapter() == CHAPTER_TEXT

    @pytest.mark.asyncio
    async def test_board_injected_via_extra_chapter_prompt_vars(
        self,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
    ) -> None:
        """The state board reflects the latest history entry per character."""
        role = _StateTestRole(name="novel-state-board")
        ctx = StateChapterContext().set_draft(sample_draft).set_characters([sample_character])
        ctx.record_chapter_states(
            ChapterStateRecord(
                characters=[
                    CharacterState(character="Hero", states=["standing"], paragraphs=[0], chapter_end_state="standing")
                ]
            )
        )
        role.extra_chapter_prompt_vars(ctx)
        assert "character_state_board" in ctx.chapter_prompt_vars
        assert "Hero: standing (end of chapter 0)" in ctx.chapter_prompt_vars["character_state_board"]

    @pytest.mark.asyncio
    async def test_no_board_without_state_context(
        self,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
    ) -> None:
        """A plain channel contributes no board vars."""
        role = _StateTestRole(name="novel-state-board-skip")
        ctx = ChapterContext().set_draft(sample_draft).set_characters([sample_character])
        assert role.extra_chapter_prompt_vars(ctx) is None
        assert ctx.chapter_prompt_vars == {}

    @pytest.mark.asyncio
    async def test_regeneration_on_violations(
        self,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """Violations trigger one regeneration; histories come from the FINAL text's record."""
        role = _StateTestRole(name="novel-state-regen")
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        ctx = (
            StateChapterContext()
            .set_draft(sample_draft)
            .set_chapter_plans(chapter_plans)
            .set_characters([sample_character])
            .set_pending_chapter(0, CHAPTER_TEXT)
        )
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
        default_json = ChapterStateRecord().model_dump_json()
        # Flat queue: real values first (propose #1, regen aask, propose #2), parseable padding after.
        responses = return_router_usage(
            rejected.model_dump_json(), rewritten, clean.model_dump_json(), default=default_json
        )
        with install_router_usage(*responses):
            await role.after_chapter_gen(ctx)

        assert ctx.pending_chapter() == rewritten
        assert ctx.state_ledger.histories == {"Hero": [(0, "standing at the door")]}
        assert role._extraction_raws == [CHAPTER_TEXT, rewritten]
        assert ctx.state_ledger.violations == ["Hero: paragraph 1 at the door with no described motion"]

    @pytest.mark.asyncio
    async def test_residual_violations_accepted_after_one_pass(
        self,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """A second violation round is accepted after exactly one regeneration; residuals logged."""
        role = _StateTestRole(name="novel-state-residual")
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        ctx = (
            StateChapterContext()
            .set_draft(sample_draft)
            .set_chapter_plans(chapter_plans)
            .set_characters([sample_character])
            .set_pending_chapter(0, CHAPTER_TEXT)
        )
        bad1 = ChapterStateRecord(
            characters=[
                CharacterState(character="Hero", states=["standing"], paragraphs=[0], chapter_end_state="standing")
            ],
            violations=["Hero: standing at the door in paragraph 1 with no described motion"],
        )
        bad2 = ChapterStateRecord(
            characters=[
                CharacterState(character="Hero", states=["standing"], paragraphs=[0], chapter_end_state="standing")
            ],
            violations=["Hero: paragraph 1 posture flip still unbridged"],
        )
        rewritten = CHAPTER_TEXT + "\n\nP2: The hero teleported to the roof."
        default_json = ChapterStateRecord().model_dump_json()
        # Flat queue: real values first (propose #1, regen aask, propose #2), parseable padding after.
        responses = return_router_usage(bad1.model_dump_json(), rewritten, bad2.model_dump_json(), default=default_json)
        with install_router_usage(*responses):
            await role.after_chapter_gen(ctx)

        assert ctx.pending_chapter() == rewritten
        assert role._extraction_raws == [CHAPTER_TEXT, rewritten]
        assert ctx.state_ledger.violations == [
            "Hero: standing at the door in paragraph 1 with no described motion",
            "Hero: paragraph 1 posture flip still unbridged",
        ]
        assert ctx.state_ledger.histories == {"Hero": [(0, "standing")]}

    @pytest.mark.asyncio
    async def test_extraction_failure_soft_skips(
        self,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """An unparseable extraction response skips the gate softly: no history, no regeneration."""
        from fabricatio_mock.models.mock_router import return_json_router_usage

        role = _StateTestRole(name="novel-state-extract-fail")
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        ctx = (
            StateChapterContext()
            .set_draft(sample_draft)
            .set_chapter_plans(chapter_plans)
            .set_characters([sample_character])
            .set_pending_chapter(0, CHAPTER_TEXT)
        )
        with install_router_usage(
            *return_json_router_usage("this is plain text, not valid json for ChapterStateRecord")
        ):
            await role.after_chapter_gen(ctx)

        assert ctx.state_ledger.histories == {}
        assert ctx.state_ledger.violations == ["State extraction failed for chapter 0 — chapter end states unknown"]
        assert ctx.pending_chapter() == CHAPTER_TEXT
        assert role._extraction_raws == [CHAPTER_TEXT]


class TestBaseSeam:
    """The base loop stages the raw chapter and keeps chapter_index() == i at every hook."""

    @pytest.mark.asyncio
    async def test_loop_stages_pending_and_preserves_invariant(
        self,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """The raw chapter is staged before after_chapter_gen and all hooks see chapter_index() == i."""
        role = _RecordingRole(name="novel-base-seam")
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        summary = ChapterSummary(key_events=[], character_states={})
        responses = return_router_usage(CHAPTER_TEXT, default=summary.model_dump_json())
        with install_router_usage(*responses):
            contents = await role.create_chapters(sample_draft, chapter_plans, [sample_character])

        assert contents == [CHAPTER_TEXT]
        assert role._hook_indexes == {"prepare": 0, "after_gen": 0, "after_summarize": 0}
        assert role._pending_at_hook["prepare"] is None
        assert role._pending_at_hook["after_gen"] == CHAPTER_TEXT
        assert role._pending_at_hook["after_summarize"] == CHAPTER_TEXT
        assert role._current_summary_ok


def _make_doc(content: str) -> WritingStyleDocument:
    """Build a WritingStyleDocument for diamond test fixtures."""
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


class StateMentalRAGChapterContext(StateChapterContext, MentalChapterContext, RAGChapterContext):
    """Carries state histories, mental states, and RAG config in one channel."""


class _DiamondRole(LLMTestRole, NovelComposeState, NovelComposeMental, NovelComposeRAG):
    """Three-way diamond: state + mental + RAG compose on the base hooks."""

    _docs_by_query: Dict[str, List[WritingStyleDocument]] = PrivateAttr(default_factory=dict)

    @property
    def docs_by_query(self) -> Dict[str, List[WritingStyleDocument]]:
        """Mapping of query -> returned docs."""
        return self._docs_by_query

    @docs_by_query.setter
    def docs_by_query(self, value: Dict[str, List[WritingStyleDocument]]) -> None:
        self._docs_by_query = value

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
        """Return docs in reverse (deterministic order)."""
        return list(reversed(documents))

    async def build_chapter_context(self, characters: List[CharacterCard]) -> StateMentalRAGChapterContext:
        return StateMentalRAGChapterContext(character_states=await self.seed_mental_states(characters))


class TestStateDiamond:
    """State + mental + RAG compose through cooperative hooks on one channel."""

    @pytest.mark.asyncio
    async def test_extra_vars_merge_both_boards(
        self,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
    ) -> None:
        """Both feature boards land on the channel through the cooperative extra_chapter_prompt_vars."""
        from fabricatio_character.models.mental import MentalState

        role = _DiamondRole(name="novel-diamond-vars")
        ctx = (
            StateMentalRAGChapterContext(
                character_states={sample_character.name: MentalState.from_card(sample_character)}
            )
            .set_draft(sample_draft)
            .set_characters([sample_character])
        )
        ctx.record_chapter_states(
            ChapterStateRecord(
                characters=[
                    CharacterState(character="Hero", states=["standing"], paragraphs=[0], chapter_end_state="standing")
                ]
            )
        )
        role.extra_chapter_prompt_vars(ctx)
        assert "character_state_board" in ctx.chapter_prompt_vars
        assert "character_mental_states" in ctx.chapter_prompt_vars
        assert "Hero: standing (end of chapter 0)" in ctx.chapter_prompt_vars["character_state_board"]
        assert "Hero" in ctx.chapter_prompt_vars["character_mental_states"]

    @pytest.mark.asyncio
    async def test_prepare_injects_board_mental_and_style_docs(
        self,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
        sample_script: Script,
    ) -> None:
        """The rendered prompt carries the state board, mental states, and injected style docs."""
        from fabricatio_character.models.mental import MentalState

        role = _DiamondRole(name="novel-diamond-prepare")
        chapter_plans = ChapterPlan.from_draft(sample_draft, [sample_script])
        plan = chapter_plans[0]
        role.docs_by_query = {
            _fetch_query(plan.script.as_prompt()): [_make_doc("style-1")],
            _fetch_query(plan.script.scenes[0].description): [_make_doc("scene-1")],
        }
        ctx = (
            StateMentalRAGChapterContext(
                character_states={sample_character.name: MentalState.from_card(sample_character)},
                writing_style_fetch_config=WritingStyleFetchConfig(limit=3),
            )
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
        assert "Character State Board" in rendered
        assert "Character Psychological States" in rendered
        assert "Hero: standing (end of chapter 0)" in rendered


class TestStateActions:
    """State-consistency action classes shape and MRO."""

    def test_actions_inherit_capability_and_action(self) -> None:
        """`GenerateNovelState` / `GenerateChaptersFromScriptsWithState` inherit the capability and `Action`."""
        from fabricatio_core.models.action import Action
        from fabricatio_novel.actions.novel_state import (
            GenerateChaptersFromScriptsWithState,
            GenerateNovelState,
        )

        assert issubclass(GenerateNovelState, NovelComposeState)
        assert issubclass(GenerateNovelState, Action)
        assert issubclass(GenerateChaptersFromScriptsWithState, NovelComposeState)
        assert issubclass(GenerateChaptersFromScriptsWithState, Action)

    def test_actions_have_ctx_override_true(self) -> None:
        """Both actions follow project convention `ctx_override=True`."""
        from fabricatio_novel.actions.novel_state import (
            GenerateChaptersFromScriptsWithState,
            GenerateNovelState,
        )

        assert GenerateNovelState.ctx_override is True
        assert GenerateChaptersFromScriptsWithState.ctx_override is True

    def test_actions_expose_output_keys(self) -> None:
        """`output_key` defaults mirror the mental actions (`novel` / `novel_chapter_contents`)."""
        from fabricatio_novel.actions.novel_state import (
            GenerateChaptersFromScriptsWithState,
            GenerateNovelState,
        )

        assert GenerateNovelState.model_fields["output_key"].default == "novel"
        assert GenerateChaptersFromScriptsWithState.model_fields["output_key"].default == "novel_chapter_contents"

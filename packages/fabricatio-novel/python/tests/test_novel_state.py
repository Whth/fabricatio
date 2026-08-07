"""Tests for fabricatio-novel character state consistency (base seam + NovelComposeState)."""

from typing import Dict, List, Optional

import pytest
from fabricatio_character.models.character import CharacterCard
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_model_json_router_usage, return_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.capabilities.novel_state import NovelComposeState, StateChapterContext
from fabricatio_novel.models.chapter_context import ChapterContext
from fabricatio_novel.models.chapter_state import ChapterStateRecord, CharacterState
from fabricatio_novel.models.draft import ChapterDraft, NovelDraft
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
    """Mental's extra vars survive the cooperative merge unchanged when it is the sole override."""

    @pytest.mark.asyncio
    async def test_sole_override_output_preserved(self, sample_character: CharacterCard) -> None:
        """A sole mental override still contributes exactly its own board vars."""
        from fabricatio_character.models.mental import MentalState
        from fabricatio_novel.capabilities.novel_mental import MentalChapterContext, NovelComposeMental

        class _MentalRole(LLMTestRole, NovelComposeMental):
            pass

        role = _MentalRole(name="mental-merge-regression")
        ctx = MentalChapterContext(character_states={sample_character.name: MentalState.from_card(sample_character)})
        vars_ = role.extra_chapter_prompt_vars(ctx)
        assert set(vars_) == {"character_mental_states"}
        assert "Hero" in vars_["character_mental_states"]


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

        assert ctx.character_state_histories == {"Hero": [(0, "walking to the door")]}
        assert ctx.character_in_chapter_states == {"Hero": ["standing by the window", "walking to the door"]}
        assert ctx.state_violations == []
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
        vars_ = role.extra_chapter_prompt_vars(ctx)
        assert "character_state_board" in vars_
        assert "Hero: standing (end of chapter 0)" in vars_["character_state_board"]

    @pytest.mark.asyncio
    async def test_no_board_without_state_context(
        self,
        sample_draft: NovelDraft,
        sample_character: CharacterCard,
    ) -> None:
        """A plain channel contributes no board vars."""
        role = _StateTestRole(name="novel-state-board-skip")
        ctx = ChapterContext().set_draft(sample_draft).set_characters([sample_character])
        assert role.extra_chapter_prompt_vars(ctx) == {}


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

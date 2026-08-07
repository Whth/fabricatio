"""Tests for fabricatio-novel character state consistency (base seam + NovelComposeState)."""

from typing import Dict, Optional

import pytest
from fabricatio_character.models.character import CharacterCard
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.models.chapter_context import ChapterContext
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

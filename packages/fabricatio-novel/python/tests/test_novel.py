"""Test module for fabricatio-novel models, utilities, actions, and capabilities.

This module contains pytest test cases verifying the correctness of novel data models,
utility functions, the ValidateNovel action, and capability methods using fabricatio-mock.
"""

import pytest
from fabricatio_character.models.character import CharacterCard
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_model_json_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.models.draft import ChapterDraft, NovelDraft
from fabricatio_novel.models.novel import Chapter, Novel
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.scripting import Scene, Script
from fabricatio_novel.utils import formated_title

# ---------------------------------------------------------------------------
# Capability test role
# ---------------------------------------------------------------------------


class NovelRole(LLMTestRole, NovelCompose):
    """Test role that combines LLMTestRole with NovelCompose for testing."""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def chapter_draft_intro() -> ChapterDraft:
    """Create a ChapterDraft for an introduction chapter.

    Returns:
        ChapterDraft: A chapter draft with title 'Awakening' and weight 1.0.
    """
    return ChapterDraft(title="Awakening", synopsis="The hero wakes up in a strange land.", weight=1.0)


@pytest.fixture
def chapter_draft_middle() -> ChapterDraft:
    """Create a ChapterDraft for a middle chapter.

    Returns:
        ChapterDraft: A chapter draft with title 'The Journey' and weight 2.0.
    """
    return ChapterDraft(title="The Journey", synopsis="The hero travels across mountains.", weight=2.0)


@pytest.fixture
def chapter_draft_finale() -> ChapterDraft:
    """Create a ChapterDraft for the finale chapter.

    Returns:
        ChapterDraft: A chapter draft with title 'Resolution' and weight 1.0.
    """
    return ChapterDraft(title="Resolution", synopsis="The hero defeats the villain.", weight=1.0)


@pytest.fixture
def novel_draft(
    chapter_draft_intro: ChapterDraft, chapter_draft_middle: ChapterDraft, chapter_draft_finale: ChapterDraft
) -> NovelDraft:
    """Create a NovelDraft with three chapters for testing.

    Args:
        chapter_draft_intro: Fixture for the intro chapter draft.
        chapter_draft_middle: Fixture for the middle chapter draft.
        chapter_draft_finale: Fixture for the finale chapter draft.

    Returns:
        NovelDraft: A novel draft with title, genre, synopsis, characters, and chapters.
    """
    return NovelDraft(
        title="Epic Tale",
        genre=["Fantasy", "Adventure"],
        synopsis="An epic journey across a magical land.",
        character_descriptions=["A brave warrior", "A wise mage"],
        chapters=[chapter_draft_intro, chapter_draft_middle, chapter_draft_finale],
        expected_word_count=4000,
        language="English",
        sketch="",
    )


@pytest.fixture
def scene_example() -> Scene:
    """Create a Scene with a raw description.

    Returns:
        Scene: A scene with a narrative description and default weight.
    """
    return Scene.with_raw_description("The sun set over the ancient ruins.")


@pytest.fixture
def script_example(scene_example: Scene) -> Script:
    """Create a Script containing a single scene.

    Args:
        scene_example: Fixture providing a scene.

    Returns:
        Script: A script with a global prompt and one scene.
    """
    return Script(global_prompt="Write in a dark, gothic tone.", scenes=[scene_example], sketch="")


@pytest.fixture
def chapter_example() -> Chapter:
    """Create a Chapter with known content for testing.

    Returns:
        Chapter: A chapter with deterministic plain-text content.
    """
    return Chapter(
        title="Chapter 1: The Beginning",
        chapter_index=0,
        content="<p>Once upon a time there was a hero.</p>",
        expected_word_count=100,
        sketch="",
    )


@pytest.fixture
def role() -> NovelRole:
    """Create a NovelRole instance for testing.

    Returns:
        NovelRole: NovelRole instance
    """
    return NovelRole()


# ---------------------------------------------------------------------------
# Tests: utils.formated_title
# ---------------------------------------------------------------------------


class TestFormatedTitle:
    """Test suite for the formated_title utility function."""

    def test_zero_index(self) -> None:
        """Test formatting with zero-based index."""
        assert formated_title(0, "Introduction") == "Ch-0: Introduction"

    def test_positive_index(self) -> None:
        """Test formatting with a positive index."""
        assert formated_title(5, "The End") == "Ch-5: The End"

    def test_empty_title(self) -> None:
        """Test formatting with an empty title string."""
        assert formated_title(0, "") == "Ch-0: "

    def test_long_title(self) -> None:
        """Test formatting with a lengthy title."""
        title = "A Very Long Chapter Title That Goes On And On"
        assert formated_title(99, title) == f"Ch-99: {title}"


# ---------------------------------------------------------------------------
# Tests: ChapterDraft
# ---------------------------------------------------------------------------


class TestChapterDraft:
    """Test suite for the ChapterDraft model."""

    def test_creation(self, chapter_draft_intro: ChapterDraft) -> None:
        """Test basic creation and field access."""
        assert chapter_draft_intro.title == "Awakening"
        assert chapter_draft_intro.synopsis == "The hero wakes up in a strange land."
        assert chapter_draft_intro.weight == 1.0

    def test_custom_weight(self) -> None:
        """Test that a ChapterDraft can be created with a custom weight."""
        draft = ChapterDraft(title="Test", synopsis="Test synopsis.", weight=0.5)
        assert draft.weight == 0.5


# ---------------------------------------------------------------------------
# Tests: NovelDraft
# ---------------------------------------------------------------------------


class TestNovelDraft:
    """Test suite for the NovelDraft model."""

    def test_creation(self, novel_draft: NovelDraft) -> None:
        """Test basic creation and field access."""
        assert novel_draft.title == "Epic Tale"
        assert novel_draft.genre == ["Fantasy", "Adventure"]
        assert novel_draft.expected_word_count == 4000
        assert novel_draft.language == "English"

    def test_total_chapters(self, novel_draft: NovelDraft) -> None:
        """Test total_chapters returns the correct count."""
        assert novel_draft.total_chapters == 3

    def test_all_chapters_titles(self, novel_draft: NovelDraft) -> None:
        """Test all_chapters_titles returns formatted titles."""
        titles = novel_draft.all_chapters_titles
        assert titles == ["Ch-0: Awakening", "Ch-1: The Journey", "Ch-2: Resolution"]

    def test_chapter_expected_word_counts_even_weights(self) -> None:
        """Test word count distribution when all chapter weights are equal."""
        drafts = [ChapterDraft(title=f"Ch{i}", synopsis=f"Synopsis {i}", weight=1.0) for i in range(4)]
        novel = NovelDraft(
            title="Test",
            genre=["Fiction"],
            synopsis="Test.",
            character_descriptions=[],
            chapters=drafts,
            expected_word_count=1000,
            language="English",
            sketch="",
        )
        counts = novel.chapter_expected_word_counts
        assert counts == [250, 250, 250, 250]

    def test_chapter_expected_word_counts_uneven_weights(
        self,
        chapter_draft_intro: ChapterDraft,
        chapter_draft_middle: ChapterDraft,
        chapter_draft_finale: ChapterDraft,
    ) -> None:
        """Test word count distribution with weights [1.0, 2.0, 1.0] totaling 4000 words."""
        novel = NovelDraft(
            title="Test",
            genre=["Fiction"],
            synopsis="Test.",
            character_descriptions=[],
            chapters=[chapter_draft_intro, chapter_draft_middle, chapter_draft_finale],
            expected_word_count=4000,
            language="English",
            sketch="",
        )
        # weights: [1.0, 2.0, 1.0], sum=4.0
        # expected: [1000, 2000, 1000]
        counts = novel.chapter_expected_word_counts
        assert counts[0] == 1000
        assert counts[1] == 2000
        assert counts[2] == 1000
        assert sum(counts) == 4000

    def test_chapter_expected_word_counts_rounding(self) -> None:
        """Test that word count distribution handles rounding (int truncation)."""
        drafts = [
            ChapterDraft(title="A", synopsis=".", weight=1.0),
            ChapterDraft(title="B", synopsis=".", weight=1.0),
            ChapterDraft(title="C", synopsis=".", weight=1.0),
        ]
        novel = NovelDraft(
            title="Test",
            genre=["Fiction"],
            synopsis=".",
            character_descriptions=[],
            chapters=drafts,
            expected_word_count=100,
            language="English",
            sketch="",
        )
        # 100 / 3 = 33.33... -> int() truncates to 33
        counts = novel.chapter_expected_word_counts
        assert counts == [33, 33, 33]

    def test_iter_chap(self, novel_draft: NovelDraft) -> None:
        """Test iter_chap yields (index, word_count, draft) tuples."""
        results = list(novel_draft.iter_chap())
        assert len(results) == 3
        idx, wc, draft = results[0]
        assert idx == 0
        assert draft.title == "Awakening"
        assert isinstance(wc, int)
        # Sum of all word counts should equal expected_word_count
        assert sum(r[1] for r in results) == novel_draft.expected_word_count

    def test_iter_ft_chap(self, novel_draft: NovelDraft) -> None:
        """Test iter_ft_chap yields (formatted_title, word_count, draft) tuples."""
        results = list(novel_draft.iter_ft_chap())
        assert len(results) == 3
        title, wc, draft = results[0]
        assert title == "Ch-0: Awakening"
        assert isinstance(wc, int)
        assert draft.title == "Awakening"


# ---------------------------------------------------------------------------
# Tests: Scene
# ---------------------------------------------------------------------------


class TestScene:
    """Test suite for the Scene model."""

    def test_with_raw_description(self, scene_example: Scene) -> None:
        """Test factory method creates a scene with correct defaults."""
        assert scene_example.description == "The sun set over the ancient ruins."
        assert scene_example.tags == []
        assert scene_example.prompt == ""
        assert scene_example.weight == 1.0

    def test_append_prompt(self, scene_example: Scene) -> None:
        """Test append_prompt adds a prompt to the scene."""
        scene_example.append_prompt("Be poetic.")
        assert "Be poetic." in scene_example.prompt

    def test_append_prompt_chaining(self, scene_example: Scene) -> None:
        """Test append_prompt returns Self for chaining."""
        result = scene_example.append_prompt("First.")
        assert result is scene_example
        scene_example.append_prompt("Second.")
        assert "First." in scene_example.prompt
        assert "Second." in scene_example.prompt


# ---------------------------------------------------------------------------
# Tests: Script
# ---------------------------------------------------------------------------


class TestScript:
    """Test suite for the Script model."""

    def test_creation(self, script_example: Script) -> None:
        """Test basic creation and field access."""
        assert script_example.global_prompt == "Write in a dark, gothic tone."
        assert len(script_example.scenes) == 1

    def test_with_raw_synosis(self) -> None:
        """Test factory method creates a script from a synopsis string."""
        script = Script.with_raw_synosis("A lone traveler enters a dark forest.")
        assert script.global_prompt == ""
        assert len(script.scenes) == 1
        assert script.scenes[0].description == "A lone traveler enters a dark forest."
        assert script.scenes[0].weight == 1.0

    def test_append_global_prompt(self, script_example: Script) -> None:
        """Test append_global_prompt adds a prompt to the script."""
        script_example.append_global_prompt("Use short sentences.")
        assert "Use short sentences." in script_example.global_prompt

    def test_append_global_prompt_chaining(self, script_example: Script) -> None:
        """Test append_global_prompt returns Self for chaining."""
        result = script_example.append_global_prompt("Extra guidance.")
        assert result is script_example

    def test_as_prompt_inner(self, script_example: Script) -> None:
        """Test _as_prompt_inner returns a dict representation."""
        inner = script_example._as_prompt_inner()
        assert isinstance(inner, dict)
        assert "global_prompt" in inner
        assert "scenes" in inner


# ---------------------------------------------------------------------------
# Tests: Chapter
# ---------------------------------------------------------------------------


class TestChapter:
    """Test suite for the Chapter model."""

    def test_creation(self, chapter_example: Chapter) -> None:
        """Test basic creation and field access."""
        assert chapter_example.title == "Chapter 1: The Beginning"
        assert chapter_example.chapter_index == 0
        assert chapter_example.expected_word_count == 100

    def test_exact_word_count(self, chapter_example: Chapter) -> None:
        """Test exact_word_count counts all word-boundary tokens including HTML tags."""
        count = chapter_example.exact_word_count
        assert count > 0
        # Rust word_count splits by Unicode word boundaries; HTML tags count as tokens
        assert count == 16

    def test_exact_word_count_plain_text(self) -> None:
        """Test exact_word_count with plain text (no HTML)."""
        chapter = Chapter(title="Plain", chapter_index=0, content="once upon a time", expected_word_count=4, sketch="")
        assert chapter.exact_word_count == 4

    def test_exact_word_count_empty(self) -> None:
        """Test exact_word_count with empty content."""
        chapter = Chapter(title="Empty", chapter_index=0, content="", expected_word_count=0, sketch="")
        assert chapter.exact_word_count == 0

    def test_with_raw_content(self) -> None:
        """Test with_raw_content factory converts raw text to XHTML paragraphs."""
        raw = "First paragraph.\n\nSecond paragraph."
        chapter = Chapter.with_raw_content(
            raw=raw,
            title="Test Chapter",
            expected_word_count=50,
            chapter_index=0,
        )
        assert "<p>First paragraph.</p>" in chapter.content
        assert "<p>Second paragraph.</p>" in chapter.content
        assert chapter.title == "Test Chapter"
        assert chapter.expected_word_count == 50
        assert chapter.chapter_index == 0

    def test_with_raw_content_preserves_metadata(self) -> None:
        """Test with_raw_content preserves title and chapter_index."""
        chapter = Chapter.with_raw_content("Some text.", "Custom Title", 100, 2)
        assert chapter.title == "Custom Title"
        assert chapter.chapter_index == 2

    def test_from_plan_and_raw_content(self, chapter_draft_intro: ChapterDraft) -> None:
        """Test from_plan_and_raw_content factory creates a chapter from a plan."""
        script = Script.with_raw_synosis("A hero wakes up.")
        plan = ChapterPlan.new(
            draft=chapter_draft_intro,
            script=script,
            expected_word_count=500,
            chapter_index=0,
        )
        raw_text = "The hero opened his eyes and saw a new world."
        chapter = Chapter.from_plan_and_raw_content(plan, raw_text)
        assert chapter.title == "Awakening"
        assert chapter.expected_word_count == 500
        assert chapter.chapter_index == 0
        assert "<p>" in chapter.content


# ---------------------------------------------------------------------------
# Tests: Novel
# ---------------------------------------------------------------------------


class TestNovel:
    """Test suite for the Novel model."""

    @pytest.fixture
    def novel(self) -> Novel:
        """Create a Novel with two chapters for testing.

        Returns:
            Novel: A novel with two chapters of known plain-text content.
        """
        # "Hello world." = 3 tokens (Hello, world, .); "Goodbye world." = 3 tokens
        ch1 = Chapter(title="Ch1", chapter_index=0, content="Hello world.", expected_word_count=50, sketch="")
        ch2 = Chapter(title="Ch2", chapter_index=1, content="Goodbye world.", expected_word_count=50, sketch="")
        return Novel(
            title="Test Novel",
            chapters=[ch1, ch2],
            synopsis="A short test novel.",
            expected_word_count=100,
            sketch="",
        )

    def test_creation(self, novel: Novel) -> None:
        """Test basic creation and field access."""
        assert novel.title == "Test Novel"
        assert len(novel.chapters) == 2
        assert novel.synopsis == "A short test novel."
        assert novel.expected_word_count == 100

    def test_exact_word_count(self, novel: Novel) -> None:
        """Test exact_word_count sums word counts across all chapters."""
        # "Hello world." = 3 tokens, "Goodbye world." = 3 tokens
        assert novel.exact_word_count == 6

    def test_word_count_compliance_ratio(self, novel: Novel) -> None:
        """Test word_count_compliance_ratio computes correct ratio."""
        # 6 actual / 100 expected = 0.06
        assert novel.word_count_compliance_ratio == pytest.approx(0.06)

    def test_word_count_compliance_ratio_exact_match(self) -> None:
        """Test compliance ratio when word counts match exactly."""
        content = "one two three four five six seven eight nine ten"
        chapter = Chapter(title="C", chapter_index=0, content=content, expected_word_count=10, sketch="")
        novel = Novel(
            title="Exact",
            chapters=[chapter],
            synopsis=".",
            expected_word_count=10,
            sketch="",
        )
        assert novel.word_count_compliance_ratio == pytest.approx(1.0)

    def test_word_count_compliance_ratio_zero_expected(self) -> None:
        """Test compliance ratio raises on zero expected word count (division by zero)."""
        chapter = Chapter(title="C", chapter_index=0, content="Hello.", expected_word_count=0, sketch="")
        novel = Novel(
            title="Zero",
            chapters=[chapter],
            synopsis=".",
            expected_word_count=0,
            sketch="",
        )
        with pytest.raises(ZeroDivisionError):
            _ = novel.word_count_compliance_ratio


# ---------------------------------------------------------------------------
# Tests: ChapterPlan
# ---------------------------------------------------------------------------


class TestChapterPlan:
    """Test suite for the ChapterPlan model."""

    @pytest.fixture
    def plan(self, chapter_draft_intro: ChapterDraft, script_example: Script) -> ChapterPlan:
        """Create a ChapterPlan for testing.

        Args:
            chapter_draft_intro: Fixture for a chapter draft.
            script_example: Fixture for a script.

        Returns:
            ChapterPlan: A plan pairing the draft with the script.
        """
        return ChapterPlan.new(
            draft=chapter_draft_intro,
            script=script_example,
            expected_word_count=1000,
            chapter_index=0,
        )

    def test_creation(self, plan: ChapterPlan) -> None:
        """Test basic creation and field access."""
        assert plan.chapter_index == 0
        assert plan.expected_word_count == 1000
        assert plan.draft.title == "Awakening"
        assert plan.script.global_prompt == "Write in a dark, gothic tone."

    def test_formatted_chapter_title(self, plan: ChapterPlan) -> None:
        """Test formatted_chapter_title returns correct format."""
        assert plan.formatted_chapter_title == "Ch-0: Awakening"

    def test_from_draft(self, novel_draft: NovelDraft) -> None:
        """Test from_draft builds plans from a NovelDraft and matching scripts."""
        scripts = [
            Script.with_raw_synosis("Intro synopsis"),
            Script.with_raw_synosis("Middle synopsis"),
            Script.with_raw_synosis("Finale synopsis"),
        ]
        plans = ChapterPlan.from_draft(novel_draft, scripts)
        assert len(plans) == 3
        assert plans[0].draft.title == "Awakening"
        assert plans[1].draft.title == "The Journey"
        assert plans[2].draft.title == "Resolution"
        assert sum(p.expected_word_count for p in plans) == novel_draft.expected_word_count

    def test_from_draft_with_none_scripts(self, novel_draft: NovelDraft) -> None:
        """Test from_draft falls back to raw synopsis when script is None."""
        scripts = [None, None, None]
        plans = ChapterPlan.from_draft(novel_draft, scripts)
        assert len(plans) == 3
        # When script is None, it falls back to Script.with_raw_synosis(draft.synopsis)
        for plan in plans:
            assert len(plan.script.scenes) == 1
            assert plan.script.scenes[0].description == plan.draft.synopsis

    def test_from_draft_mixed_scripts(self, novel_draft: NovelDraft) -> None:
        """Test from_draft with a mix of provided and None scripts."""
        scripts: list[Script | None] = [
            Script.with_raw_synosis("Custom intro"),
            None,
            Script.with_raw_synosis("Custom finale"),
        ]
        plans = ChapterPlan.from_draft(novel_draft, scripts)
        assert len(plans) == 3
        assert plans[0].script.scenes[0].description == "Custom intro"
        # Middle falls back to draft synopsis
        assert plans[1].script.scenes[0].description == novel_draft.chapters[1].synopsis
        assert plans[2].script.scenes[0].description == "Custom finale"

    def test_with_try_script_with_script(self, chapter_draft_intro: ChapterDraft, script_example: Script) -> None:
        """Test with_try_script uses the provided script when not None."""
        plan = ChapterPlan.with_try_script(chapter_draft_intro, script_example, 500, 0)
        assert plan.script is script_example

    def test_with_try_script_with_none(self, chapter_draft_intro: ChapterDraft) -> None:
        """Test with_try_script falls back to raw synopsis when script is None."""
        plan = ChapterPlan.with_try_script(chapter_draft_intro, None, 500, 0)
        assert plan.script.scenes[0].description == chapter_draft_intro.synopsis
        assert plan.script.global_prompt == ""


# ---------------------------------------------------------------------------
# Tests: ValidateNovel (async action, no LLM)
# ---------------------------------------------------------------------------


class TestValidateNovel:
    """Test suite for the ValidateNovel action."""

    @pytest.fixture
    def valid_novel(self) -> Novel:
        """Create a novel that passes default validation (>1000 words, >0.8 ratio).

        Returns:
            Novel: A novel with 2 chapters and sufficient word count.
        """
        content = " ".join(["word"] * 600)
        chapters = [
            Chapter(title=f"Ch{i}", chapter_index=i, content=content, expected_word_count=600, sketch="")
            for i in range(2)
        ]
        return Novel(
            title="Valid Novel",
            chapters=chapters,
            synopsis="A valid novel.",
            expected_word_count=1200,
            sketch="",
        )

    @pytest.fixture
    def empty_chapters_novel(self) -> Novel:
        """Create a novel with zero chapters but non-zero expected count.

        Returns:
            Novel: A novel with zero chapters.
        """
        return Novel(
            title="Empty Novel",
            chapters=[],
            synopsis="Empty.",
            expected_word_count=1000,
            sketch="",
        )

    @pytest.fixture
    def low_word_count_novel(self) -> Novel:
        """Create a novel with too few words for default validation.

        Returns:
            Novel: A novel with 1 chapter containing very few words.
        """
        chapter = Chapter(title="Tiny", chapter_index=0, content="Hello.", expected_word_count=100, sketch="")
        return Novel(
            title="Tiny Novel",
            chapters=[chapter],
            synopsis="A tiny novel.",
            expected_word_count=100,
            sketch="",
        )

    @pytest.mark.asyncio
    async def test_valid_novel_passes(self, valid_novel: Novel) -> None:
        """Test that a well-formed novel passes default validation."""
        from fabricatio_novel.actions.novel import ValidateNovel

        validator = ValidateNovel(name="test", description="test validator", novel=valid_novel)
        result = await validator._execute()
        assert result is True

    @pytest.mark.asyncio
    async def test_too_few_chapters_fails(self, empty_chapters_novel: Novel) -> None:
        """Test that a novel with zero chapters fails validation."""
        from fabricatio_novel.actions.novel import ValidateNovel

        validator = ValidateNovel(name="test", description="test validator", novel=empty_chapters_novel)
        result = await validator._execute()
        assert result is False

    @pytest.mark.asyncio
    async def test_low_word_count_fails(self, low_word_count_novel: Novel) -> None:
        """Test that a novel with too few words fails validation."""
        from fabricatio_novel.actions.novel import ValidateNovel

        validator = ValidateNovel(name="test", description="test validator", novel=low_word_count_novel)
        result = await validator._execute()
        assert result is False

    @pytest.mark.asyncio
    async def test_custom_thresholds_pass(self, low_word_count_novel: Novel) -> None:
        """Test validation passes when custom thresholds are relaxed."""
        from fabricatio_novel.actions.novel import ValidateNovel

        validator = ValidateNovel(
            name="test",
            description="test validator",
            novel=low_word_count_novel,
            min_chapters=1,
            min_total_words=1,
            min_compliance_ratio=0.01,
        )
        result = await validator._execute()
        assert result is True

    @pytest.mark.asyncio
    async def test_custom_thresholds_fail_min_chapters(self, valid_novel: Novel) -> None:
        """Test validation fails when min_chapters exceeds actual count."""
        from fabricatio_novel.actions.novel import ValidateNovel

        validator = ValidateNovel(
            name="test",
            description="test validator",
            novel=valid_novel,
            min_chapters=100,
        )
        result = await validator._execute()
        assert result is False

    @pytest.mark.asyncio
    async def test_custom_thresholds_fail_min_words(self, valid_novel: Novel) -> None:
        """Test validation fails when min_total_words exceeds actual count."""
        from fabricatio_novel.actions.novel import ValidateNovel

        validator = ValidateNovel(
            name="test",
            description="test validator",
            novel=valid_novel,
            min_total_words=999_999,
        )
        result = await validator._execute()
        assert result is False

    @pytest.mark.asyncio
    async def test_custom_thresholds_fail_compliance_ratio(self, low_word_count_novel: Novel) -> None:
        """Test validation fails when compliance ratio threshold is unmet."""
        from fabricatio_novel.actions.novel import ValidateNovel

        validator = ValidateNovel(
            name="test",
            description="test validator",
            novel=low_word_count_novel,
            min_compliance_ratio=0.99,
        )
        result = await validator._execute()
        assert result is False


# ---------------------------------------------------------------------------
# Tests: text_to_xhtml_paragraphs (Rust binding)
# ---------------------------------------------------------------------------


class TestTextToXhtmlParagraphs:
    """Test suite for the text_to_xhtml_paragraphs Rust binding."""

    def test_single_paragraph(self) -> None:
        """Test conversion of a single paragraph."""
        from fabricatio_novel.rust import text_to_xhtml_paragraphs

        result = text_to_xhtml_paragraphs("Hello world.")
        assert result == "<p>Hello world.</p>"

    def test_multiple_paragraphs(self) -> None:
        """Test conversion of multiple paragraphs separated by blank lines."""
        from fabricatio_novel.rust import text_to_xhtml_paragraphs

        result = text_to_xhtml_paragraphs("First.\n\nSecond.\n\nThird.")
        assert result == "<p>First.</p>\n<p>Second.</p>\n<p>Third.</p>"

    def test_trim_whitespace(self) -> None:
        """Test that leading/trailing whitespace is trimmed from paragraphs."""
        from fabricatio_novel.rust import text_to_xhtml_paragraphs

        result = text_to_xhtml_paragraphs("  spaced out  ")
        assert result == "<p>spaced out</p>"

    def test_empty_input(self) -> None:
        """Test that empty input produces empty output."""
        from fabricatio_novel.rust import text_to_xhtml_paragraphs

        result = text_to_xhtml_paragraphs("")
        assert result == ""

    def test_whitespace_only_input(self) -> None:
        """Test that whitespace-only input produces empty output."""
        from fabricatio_novel.rust import text_to_xhtml_paragraphs

        result = text_to_xhtml_paragraphs("   \n\n   ")
        assert result == ""


# ---------------------------------------------------------------------------
# Tests: assemble_novel (static, no LLM)
# ---------------------------------------------------------------------------


class TestAssembleNovel:
    """Test suite for the NovelCompose.assemble_novel static method."""

    def test_assemble_basic(self) -> None:
        """Test assembling a novel from draft, plans, and contents."""
        draft = NovelDraft(
            title="My Novel",
            genre=["Fiction"],
            synopsis="A test.",
            character_descriptions=[],
            chapters=[
                ChapterDraft(title="Intro", synopsis=".", weight=1.0),
                ChapterDraft(title="End", synopsis=".", weight=1.0),
            ],
            expected_word_count=200,
            language="English",
            sketch="",
        )
        plans = [
            ChapterPlan.new(
                draft=draft.chapters[0], script=Script.with_raw_synosis("."), expected_word_count=100, chapter_index=0
            ),
            ChapterPlan.new(
                draft=draft.chapters[1], script=Script.with_raw_synosis("."), expected_word_count=100, chapter_index=1
            ),
        ]
        contents = ["Once upon a time.", "The end."]

        novel = NovelCompose.assemble_novel(draft, plans, contents)
        assert novel.title == "My Novel"
        assert novel.synopsis == "A test."
        assert len(novel.chapters) == 2
        assert novel.chapters[0].title == "Intro"
        assert novel.chapters[0].chapter_index == 0
        assert novel.chapters[1].title == "End"
        assert novel.chapters[1].chapter_index == 1
        assert novel.expected_word_count == 200
        # content is wrapped in <p> tags by from_plan_and_raw_content
        assert "<p>" in novel.chapters[0].content

    def test_assemble_word_count_propagation(self) -> None:
        """Test that expected_word_count propagates from plans to chapters."""
        draft = NovelDraft(
            title="WC",
            genre=["Fiction"],
            synopsis=".",
            character_descriptions=[],
            chapters=[
                ChapterDraft(title="A", synopsis=".", weight=1.0),
            ],
            expected_word_count=500,
            language="English",
            sketch="",
        )
        plans = [
            ChapterPlan.new(
                draft=draft.chapters[0], script=Script.with_raw_synosis("."), expected_word_count=500, chapter_index=0
            ),
        ]
        contents = ["A chapter with enough words to test."]

        novel = NovelCompose.assemble_novel(draft, plans, contents)
        assert novel.chapters[0].expected_word_count == 500
        assert novel.expected_word_count == 500


# ---------------------------------------------------------------------------
# Tests: capability methods with mock LLM (async)
# ---------------------------------------------------------------------------


class TestNovelCapabilities:
    """Test suite for NovelCompose capability methods using fabricatio-mock."""

    @pytest.fixture
    def sample_draft(self) -> NovelDraft:
        """Create a sample NovelDraft for mock-based tests.

        Returns:
            NovelDraft: A minimal draft for testing.
        """
        return NovelDraft(
            title="Draft",
            genre=["Fiction"],
            synopsis="A draft.",
            character_descriptions=["A hero"],
            chapters=[ChapterDraft(title="Ch1", synopsis="Hero starts.", weight=1.0)],
            expected_word_count=100,
            language="English",
            sketch="",
        )

    @pytest.fixture
    def sample_character(self) -> CharacterCard:
        """Create a sample CharacterCard for mock-based tests.

        Returns:
            CharacterCard: A character card for testing.
        """
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
    def sample_script(self) -> Script:
        """Create a sample Script for mock-based tests.

        Returns:
            Script: A script for testing.
        """
        return Script.with_raw_synosis("The hero begins the journey.")

    @pytest.mark.asyncio
    async def test_create_draft(self, role: NovelRole, sample_draft: NovelDraft) -> None:
        """Test create_draft returns a NovelDraft from mocked LLM response."""
        responses = return_model_json_router_usage(sample_draft)
        with install_router_usage(*responses):
            result = await role.create_draft("A story about a hero.")
            assert result is not None
            assert result.title == "Draft"
            assert result.expected_word_count == 100

    @pytest.mark.asyncio
    async def test_create_characters(
        self, role: NovelRole, sample_draft: NovelDraft, sample_character: CharacterCard
    ) -> None:
        """Test create_characters returns CharacterCards from mocked LLM response."""
        responses = return_model_json_router_usage(sample_character)
        with install_router_usage(*responses):
            result = await role.create_characters(sample_draft)
            assert result is not None
            assert len(result) == 1
            assert result[0].name == "Hero"

    @pytest.mark.asyncio
    async def test_create_scripts(
        self, role: NovelRole, sample_draft: NovelDraft, sample_character: CharacterCard, sample_script: Script
    ) -> None:
        """Test create_scripts returns Scripts from mocked LLM response."""
        responses = return_model_json_router_usage(sample_script)
        with install_router_usage(*responses):
            result = await role.create_scripts(sample_draft, [sample_character])
            assert result is not None
            assert len(result) == 1
            assert result[0].scenes[0].description == "The hero begins the journey."

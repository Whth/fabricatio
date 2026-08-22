"""Model-level tests for fabricatio-novel: contexts, spans, assembly, and exports."""

from pathlib import Path

import pytest
from _support import card, prefix_log
from fabricatio_novel.models.context.base import CharacterSpan, derive_child_spans
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.models.plan import ChapterPlan, NovelPlan, ScenePlan, StoryPlan
from fabricatio_novel.models.scene import Scene
from fabricatio_novel.models.series_book import SeriesBible


class TestNovelContext:
    """Test suite for NovelContext."""

    def test_create_detects_language(self) -> None:
        """Assert create detects the outline language and initializes empty context fields."""
        ctx = NovelContext.create("少年踏上旅途。")
        assert ctx.language == "简体中文"
        assert ctx.outline == "少年踏上旅途。"
        assert ctx.title == ""
        assert ctx.description == ""
        assert ctx.series_bible is None
        assert ctx.chapter_context == []

    def test_create_with_explicit_language(self) -> None:
        """Assert an explicitly passed language overrides automatic detection."""
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        assert ctx.language == "English"

    def test_update_from_adopts_plan_fields(self) -> None:
        """Assert update_from copies the plan fields into the context and returns self."""
        ctx = NovelContext.create("The hero.", language="English")
        plan = NovelPlan(
            title="The Search",
            description="A hero searching.",
            expected_word_count=100,
            writing_constraint="First person view throughout.",
            series_bible=SeriesBible(characters=["Hero — brave protagonist."]),
        )
        result = ctx.update_from(plan)
        assert result is ctx
        assert ctx.title == "The Search"
        assert ctx.description == "A hero searching."
        assert ctx.expected_word_count == 100
        assert ctx.writing_constraint == "First person view throughout."
        assert ctx.series_bible == plan.series_bible

    def test_update_from_keeps_intent_when_plan_constraint_empty(self) -> None:
        """Assert the author's stated constraint survives an empty plan constraint."""
        ctx = NovelContext.create("The hero.", language="English")
        ctx.set_writing_constraint("I hope the novel is first person view.")
        plan = NovelPlan(title="The Search", description="A hero searching.", expected_word_count=100)
        ctx.update_from(plan)
        assert ctx.writing_constraint == "I hope the novel is first person view."

    def test_update_from_keeps_preset_bible_when_plan_bible_empty(self) -> None:
        """Assert a preset series bible survives update_from with an empty-plan bible."""
        ctx = NovelContext.create("The hero.", language="English")
        bible = SeriesBible(characters=["Hero — brave protagonist."])
        ctx.set_series_bible(bible)
        plan = NovelPlan(title="The Search", description="A hero searching.", expected_word_count=100)
        ctx.update_from(plan)
        assert ctx.title == "The Search"
        assert ctx.series_bible is bible

    def test_update_from_rejects_non_plan(self) -> None:
        """Assert update_from raises TypeError when given a non-plan value."""
        ctx = NovelContext.create("The hero.", language="English")
        with pytest.raises(TypeError):
            ctx.update_from("not a plan")  # type: ignore[arg-type]

    def test_contexts_are_chainable(self) -> None:
        """Assert chained setters attach plans and children across every context level."""
        scene = (
            SceneContext(title="S1", description="Leaving home.", expected_word_count=100)
            .set_language("English")
            .set_content("He left.")
            .set_prefix_log(prefix_log("Before.", title="S1"))
            .set_writing_constraint("First person view throughout.")
            .set_scene_plan(ScenePlan(title="S1", description="Leaving home."))
        )
        story = StoryContext(title="St1", description="The departure.", expected_word_count=100)
        story.add_scene_context(scene)
        story.set_story_plan(StoryPlan(title="St1", description="The departure."))
        chapter = ChapterContext(title="Ch1", description="The start.", expected_word_count=100)
        chapter.add_story_context(story)
        chapter.set_chapter_plan(ChapterPlan(title="Ch1", description="The start."))
        novel = NovelContext.create("The hero.", language="English")
        novel.add_chapter_context(chapter)
        novel.set_novel_plan(
            NovelPlan(title="The Hero", description="A hero.", expected_word_count=100, series_bible=SeriesBible())
        )

        assert scene.title == "S1"
        assert scene.content == "He left."
        assert scene.prefix_log.render() == "Before."
        assert scene.language == "English"
        assert scene.writing_constraint == "First person view throughout."
        assert story.scene_context == [scene]
        assert chapter.story_context == [story]
        assert novel.chapter_context == [chapter]
        assert novel.novel_plan is not None
        assert novel.novel_plan.title == "The Hero"
        assert chapter.chapter_plan is not None
        assert chapter.chapter_plan.title == "Ch1"
        assert story.story_plan is not None
        assert story.story_plan.title == "St1"
        assert scene.scene_plan is not None
        assert scene.scene_plan.title == "S1"


class TestCharacterSpan:
    """Test suite for CharacterSpan."""

    def test_dump_to_prompt_renders_start_and_end(self) -> None:
        """Assert dump_to_prompt shows both states as Initial and finalizing."""
        start = card()
        end = card().model_copy(update={"look": "scarred"})
        span = CharacterSpan(start=start, end=end)
        prompt = span.dump_to_prompt()
        assert prompt.startswith("Initial State:")
        assert "finalizing State:" in prompt
        assert prompt.count("# Name") == 2
        assert prompt.count("## Look") == 2
        assert "tall" in prompt
        assert "scarred" in prompt

    def test_dump_to_prompt_with_same_start_and_end(self) -> None:
        """Assert a span whose end equals its start renders the same card twice."""
        start = card()
        span = CharacterSpan(start=start, end=start.model_copy(deep=True))
        prompt = span.dump_to_prompt()
        assert prompt.count("# Name") == 2
        assert "Initial State:" in prompt
        assert "finalizing State:" in prompt

    def test_derive_child_spans_stitches_boundaries_between_parent_ends(self) -> None:
        """Assert N children need N-1 boundary cards; the parent ends anchor the chain."""
        start = card()
        b1 = start.model_copy(update={"act": "cautious"})
        b2 = start.model_copy(update={"flaw": "distrustful"})
        end = start.model_copy(update={"look": "wounded"})
        spans = derive_child_spans(CharacterSpan(start=start, end=end), [b1, b2])
        assert len(spans) == 3
        assert [s.start for s in spans] == [start, b1, b2]
        assert [s.end for s in spans] == [b1, b2, end]
        # the chain is continuous by construction
        assert spans[0].end is spans[1].start
        assert spans[1].end is spans[2].start

    def test_derive_child_spans_without_boundaries_returns_single_span(self) -> None:
        """Assert one child inherits the parent span unchanged when no boundaries are drafted."""
        start = card()
        end = start.model_copy(update={"look": "wounded"})
        spans = derive_child_spans(CharacterSpan(start=start, end=end), [])
        assert len(spans) == 1
        assert spans[0].start is start
        assert spans[0].end is end


class TestFromContext:
    """Test suite for the from_context assembly methods."""

    def test_scene_from_context(self) -> None:
        """Assert Scene.from_context materializes the scene fields from its context."""
        ctx = SceneContext(title="Departure", description="The hero leaves.", expected_word_count=50)
        ctx.content = "He walked out."
        scene = Scene.from_context(ctx)
        assert scene.title == "Departure"
        assert scene.description == "The hero leaves."
        assert scene.content == "He walked out."
        assert scene.expected_word_count == 50

    def test_from_plan_copies_plan_fields(self) -> None:
        """Assert SceneContext.from_plan copies plan fields and keeps the plan reference."""
        plan = ScenePlan(title="S1", description="The descent.", weight=1.0, writing_style="Gothic, lyrical prose.")
        ctx = SceneContext.from_plan(plan, expected_word_count=300)
        assert ctx.title == "S1"
        assert ctx.description == "The descent."
        assert ctx.expected_word_count == 300
        assert ctx.writing_styles == []
        assert ctx.scene_plan is plan

    def test_plans_default_to_empty_cast(self) -> None:
        """Assert every weighted plan proposes an empty cast unless the planner names one."""
        assert ScenePlan(title="S1", description="D").cast == []
        assert StoryPlan(title="St1", description="D").cast == []
        assert ChapterPlan(title="C1", description="D").cast == []

    def test_from_plan_copies_cast(self) -> None:
        """Assert from_plan copies the proposed cast onto every context level."""
        scene = SceneContext.from_plan(ScenePlan(title="S1", description="D", cast=["Hero", "Villain"]), 100)
        story = StoryContext.from_plan(StoryPlan(title="St1", description="D", cast=["Hero"]), 300)
        chapter = ChapterContext.from_plan(ChapterPlan(title="C1", description="D", cast=["Hero"]), 1000)
        assert scene.cast == ["Hero", "Villain"]
        assert story.cast == ["Hero"]
        assert chapter.cast == ["Hero"]

    def test_novel_from_context_assembles_full_tree(self) -> None:
        """Assert Novel.from_context assembles the full chapter, story, and scene tree."""
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.title = "The Search"
        ctx.description = "A hero searching."
        ctx.expected_word_count = 200
        bible = SeriesBible(characters=["Hero — brave protagonist."])
        ctx.set_series_bible(bible)

        chapter_ctx = ChapterContext(title="Ch1", description="The start.")
        story_ctx = StoryContext(title="St1", description="The departure.")
        scene_ctx = SceneContext(title="S1", description="Leaving home.", expected_word_count=100)
        scene_ctx.content = "He left."
        story_ctx.scene_context.append(scene_ctx)
        chapter_ctx.story_context.append(story_ctx)
        ctx.chapter_context.append(chapter_ctx)

        novel = Novel.from_context(ctx)
        assert novel.title == "The Search"
        assert len(novel.chapter) == 1
        assert novel.chapter[0].title == "Ch1"
        assert novel.chapter[0].story[0].title == "St1"
        assert novel.chapter[0].story[0].scenes[0].content == "He left."
        assert novel.series_bible is ctx.series_bible


class TestNovelEpub:
    """Test suite for Novel.dump_epub."""

    def test_dump_epub_builds_valid_structure(self, tmp_path: Path) -> None:
        """Assert dump_epub produces a valid EPUB with mimetype first, chapter, font, and cover."""
        import zipfile

        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.title = "The Search"
        ctx.description = "A hero searching."
        ctx.expected_word_count = 100
        chapter_ctx = ChapterContext(title="Ch1", description="The start.")
        story_ctx = StoryContext(title="St1", description="The departure.")
        scene_ctx = SceneContext(title="S1", description="Leaving home.", expected_word_count=100)
        scene_ctx.content = "He left.\n\nHe walked into the dark."
        story_ctx.scene_context.append(scene_ctx)
        chapter_ctx.story_context.append(story_ctx)
        ctx.chapter_context.append(chapter_ctx)
        novel = Novel.from_context(ctx)

        font_file = tmp_path / "custom.ttf"
        font_file.write_bytes(b"\x00\x01fake font bytes")
        cover_file = tmp_path / "cover.png"
        cover_file.write_bytes(b"\x89PNG\r\n\x1a\nfake image bytes")
        path = novel.dump_epub(tmp_path / "novel.epub", font=font_file, cover=cover_file)
        assert path.exists()
        assert path.stat().st_size > 0

        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            assert names[0] == "mimetype", f"mimetype must be the first entry, got {names[:3]}"
            assert zf.read("mimetype") == b"application/epub+zip"
            assert "META-INF/container.xml" in names
            assert any(name.endswith("nav.xhtml") for name in names)
            chapter_files = [n for n in names if n.endswith(".xhtml") and not n.endswith("nav.xhtml")]
            assert len(chapter_files) == 1, f"expected 1 chapter xhtml, got {chapter_files}"
            assert "He walked into the dark." in zf.read(chapter_files[0]).decode("utf-8")
            assert any(n.endswith("fonts/custom.ttf") for n in names), f"expected embedded font, got {names}"
            assert any(n.endswith("cover.png") for n in names), f"expected cover image, got {names}"
            css_file = next(n for n in names if n.endswith(".css"))
            assert "custom" in zf.read(css_file).decode("utf-8"), "font-family rule must reference the embedded font"


class TestNovelTexts:
    """Test suite for Novel.dump_texts."""

    @staticmethod
    def _novel_with_chapters(count: int) -> Novel:
        """Build a novel whose chapters each carry one story with one scene of distinct prose."""
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.title = "The Search"
        ctx.description = "A hero searching."
        ctx.expected_word_count = 100
        for index in range(1, count + 1):
            chapter_ctx = ChapterContext(title=f"Ch{index}", description=f"Chapter {index}.")
            story_ctx = StoryContext(title=f"St{index}", description="The departure.")
            scene_ctx = SceneContext(title="S1", description="Leaving home.", expected_word_count=100)
            scene_ctx.content = f"He left {index}.\n\nHe walked into the dark."
            story_ctx.scene_context.append(scene_ctx)
            chapter_ctx.story_context.append(story_ctx)
            ctx.chapter_context.append(chapter_ctx)
        return Novel.from_context(ctx)

    def test_dump_texts_writes_prose_per_chapter(self, tmp_path: Path) -> None:
        """Assert dump_texts writes zero-padded prose-only files named by chapter index."""
        novel = self._novel_with_chapters(3)

        out = novel.dump_texts(tmp_path / "chapters")

        assert out == tmp_path / "chapters"
        assert sorted(p.name for p in out.iterdir()) == ["01.txt", "02.txt", "03.txt"]
        body = (out / "02.txt").read_text(encoding="utf-8")
        assert body == "He left 2.\n\nHe walked into the dark."
        assert "<" not in body, "txt export must be plain prose without xhtml markup"

    def test_dump_texts_widens_padding_past_ninety_nine_chapters(self, tmp_path: Path) -> None:
        """Assert filename padding widens beyond 99 chapters so names keep sorting by index."""
        novel = self._novel_with_chapters(100)

        out = novel.dump_texts(tmp_path / "chapters")

        names = sorted(p.name for p in out.iterdir())
        assert len(names) == 100
        assert names[0] == "001.txt"
        assert names[-1] == "100.txt"

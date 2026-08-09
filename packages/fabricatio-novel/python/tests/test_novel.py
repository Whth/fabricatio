"""Test module for fabricatio-novel contexts, models, and generation capabilities."""

from pathlib import Path
from typing import List

import pytest
from fabricatio_character.models.character import CharacterCard, CharacterCardDiff
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import (
    Value,
    return_json_router_usage,
    return_mixed_router_usage,
    return_model_json_router_usage,
    return_router_usage,
)
from fabricatio_mock.utils import code_block, generic_block, install_router_usage
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.capabilities.rag import RAGCompose
from fabricatio_novel.capabilities.scene import capture_scene
from fabricatio_novel.models.context.base import CharactorTrace
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.models.plan import ChapterPlan, NovelPlan, ScenePlan, StoryPlan
from fabricatio_novel.models.rag import WritingStyleDocument, WritingStyleFetchConfig
from fabricatio_novel.models.scene import Scene
from fabricatio_novel.models.series_book import SeriesBible


def card(name: str = "Hero", look: str = "tall") -> CharacterCard:
    return CharacterCard(name=name, role="protagonist", look=look, act="brave", want="seek truth", flaw="stubborn")


def raw_value(text: str) -> Value[str]:
    """Wrap a plain scene response for mixed router usage."""
    return Value(text, "raw", convertor=lambda s: s)


class TestNovelContext:
    """Test suite for NovelContext."""

    def test_create_detects_language(self) -> None:
        ctx = NovelContext.create("少年踏上旅途。")
        assert ctx.language == "简体中文"
        assert ctx.outline == "少年踏上旅途。"
        assert ctx.title == ""
        assert ctx.description == ""
        assert ctx.series_bible is None
        assert ctx.chapter_context == []

    def test_create_with_explicit_language(self) -> None:
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        assert ctx.language == "English"

    def test_update_from_adopts_plan_fields(self) -> None:
        ctx = NovelContext.create("The hero.", language="English")
        plan = NovelPlan(
            title="The Search",
            description="A hero searching.",
            expected_word_count=100,
            series_bible=SeriesBible(characters="Hero — brave protagonist."),
        )
        result = ctx.update_from(plan)
        assert result is ctx
        assert ctx.title == "The Search"
        assert ctx.description == "A hero searching."
        assert ctx.expected_word_count == 100
        assert ctx.series_bible == plan.series_bible

    def test_update_from_keeps_preset_bible_when_plan_bible_empty(self) -> None:
        ctx = NovelContext.create("The hero.", language="English")
        bible = SeriesBible(characters="Hero — brave protagonist.")
        ctx.set_series_bible(bible)
        plan = NovelPlan(title="The Search", description="A hero searching.", expected_word_count=100)
        ctx.update_from(plan)
        assert ctx.title == "The Search"
        assert ctx.series_bible is bible

    def test_update_from_rejects_non_plan(self) -> None:
        ctx = NovelContext.create("The hero.", language="English")
        with pytest.raises(TypeError):
            ctx.update_from("not a plan")  # type: ignore[arg-type]

    def test_contexts_are_chainable(self) -> None:
        scene = (
            SceneContext(title="S1", description="Leaving home.", expected_word_count=100)
            .set_language("English")
            .set_content("He left.")
            .set_prefixed_content("Before.")
            .set_scene_plan(ScenePlan(title="S1", description="Leaving home.", expected_word_count=100))
        )
        story = StoryContext(title="St1", description="The departure.", expected_word_count=100)
        story.add_scene_context(scene)
        story.set_story_plan(StoryPlan(title="St1", description="The departure.", expected_word_count=100))
        chapter = ChapterContext(title="Ch1", description="The start.", expected_word_count=100)
        chapter.add_story_context(story)
        chapter.set_chapter_plan(ChapterPlan(title="Ch1", description="The start.", expected_word_count=100))
        novel = NovelContext.create("The hero.", language="English")
        novel.add_chapter_context(chapter)
        novel.set_novel_plan(
            NovelPlan(title="The Hero", description="A hero.", expected_word_count=100, series_bible=SeriesBible())
        )

        assert scene.title == "S1"
        assert scene.content == "He left."
        assert scene.prefixed_content == "Before."
        assert scene.language == "English"
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


class TestCharactorTrace:
    """Test suite for CharactorTrace."""

    def test_iter_charactor_cards_applies_diffs_in_order(self) -> None:
        start = card()
        trace = CharactorTrace(
            start=start,
            end=start.apply(CharacterCardDiff(look="scarred")),
            interpolates=[CharacterCardDiff(look="scarred")],
        )
        cards: List[CharacterCard] = list(trace.iter_charactor_cards())
        assert cards[0] is start
        assert [c.look for c in cards] == ["tall", "scarred", "scarred"]
        assert cards[-1] is trace.end

    def test_intepl_replaces_interpolates_and_returns_self(self) -> None:
        start = card()
        trace = CharactorTrace(start=start, end=start)
        diff = CharacterCardDiff(look="wounded")
        assert trace.intepl([diff]) is trace
        assert trace.interpolates == [diff]


class TestFromContext:
    """Test suite for the from_context assembly methods."""

    def test_scene_from_context(self) -> None:
        ctx = SceneContext(title="Departure", description="The hero leaves.", expected_word_count=50)
        ctx.content = "He walked out."
        scene = Scene.from_context(ctx)
        assert scene.title == "Departure"
        assert scene.description == "The hero leaves."
        assert scene.content == "He walked out."
        assert scene.expected_word_count == 50

    def test_novel_from_context_assembles_full_tree(self) -> None:
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.title = "The Search"
        ctx.description = "A hero searching."
        ctx.expected_word_count = 200
        bible = SeriesBible(characters="Hero — brave protagonist.")
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


class NovelRole(LLMTestRole, NovelCompose):
    """Test role combining mock LLM with the novel composition chain."""


class TestCaptureScene:
    """Test suite for the plain-text scene response capture."""

    def test_captures_heading_quote_and_prose(self) -> None:
        scene = capture_scene("### S1\n\n> Leaving home.\n\nHe left.\n\nHe walked on.")
        assert scene is not None
        assert scene.title == "S1"
        assert scene.description == "Leaving home."
        assert scene.content == "He left.\n\nHe walked on."

    def test_rejects_missing_structure(self) -> None:
        assert capture_scene("Just prose.") is None
        assert capture_scene("## S1\n\n> Leaving home.\n\nHe left.") is None
        assert capture_scene("### S1\n\nHe left.") is None


class TestNovelCompose:
    """Test suite for the generation chain with mock LLM."""

    async def test_compose_scene_writes_content_back_to_context(self) -> None:
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="Departure", description="The hero leaves home.", expected_word_count=50)
        with install_router_usage(*return_router_usage("### Departure\n\n> The hero leaves home.\n\nHe walked out.")):
            scene = await role.compose_scene(ctx)
        assert scene is not None
        assert scene.content == "He walked out."
        assert scene.expected_word_count == 50
        assert ctx.content == "He walked out."

    async def test_compose_scene_evolves_charactor_trace(self) -> None:
        role = NovelRole(name="novel_role")
        trace = CharactorTrace(start=card(), end=card())
        ctx = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)
        ctx.charactor_trace.append(trace)
        expected_diff = CharacterCardDiff(look="scarred")
        with install_router_usage(
            *return_mixed_router_usage(
                raw_value("### Battle\n\n> The hero fights.\n\nHe fought."),
                Value(expected_diff, "model"),
            )
        ):
            scene = await role.compose_scene(ctx)
        assert scene is not None
        assert trace.interpolates == [expected_diff]
        assert trace.end.look == "scarred"

    async def test_compose_novel_end_to_end(self) -> None:
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        chapter_ctx = ChapterContext(title="Ch1", description="The hero sets out.")
        story_ctx = StoryContext(title="St1", description="The departure.")
        scene_1 = SceneContext(title="S1", description="Leaving home.", expected_word_count=20)
        scene_2 = SceneContext(title="S2", description="A stranger appears.", expected_word_count=20)
        story_ctx.scene_context.extend([scene_1, scene_2])
        chapter_ctx.story_context.append(story_ctx)
        ctx.chapter_context.append(chapter_ctx)

        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=40,
            series_bible=SeriesBible(),
        )

        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                raw_value("### S1\n\n> Leaving home.\n\nHe left."),
                raw_value("### S2\n\n> A stranger appears.\n\nA stranger appeared."),
            )
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.title == "The Search"
        assert len(novel.chapter) == 1
        assert len(novel.chapter[0].story) == 1
        assert len(novel.chapter[0].story[0].scenes) == 2
        assert novel.chapter[0].story[0].scenes[1].content == "A stranger appeared."
        assert ctx.title == "The Search"
        assert ctx.chapter_context[0].story_context[0].scene_context[1].content == "A stranger appeared."
        assert ctx.chapter_context[0].story_context[0].scene_context[1].prefixed_content == (
            "### S1\n\n> Leaving home.\n\nHe left."
        )
        assert ctx.chapter_context[0].story_context[0].scene_context[0].prefixed_content == ""

    async def test_compose_novel_returns_none_when_metadata_fails(self) -> None:
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero.", language="English")
        with install_router_usage("not valid json", "", ""):
            novel = await role.compose_novel(ctx)
        assert novel is None

    async def test_prepare_scene_requirement_renders_prefixed_content_after_static_head(self) -> None:
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.prefixed_content = "He walked into the dark."

        requirement = await role.prepare_scene_requirement(ctx)

        # the static head (incl. per-run language) leads so it stays prefix-cacheable
        assert requirement.startswith("# Scene Writing")
        assert requirement.index("Respond entirely in") < requirement.index("# Previous Content")
        assert requirement.index("He walked into the dark.") > requirement.index("# Previous Content")
        assert requirement.index("A stranger appears.") > requirement.index("## Scene")
        # the per-scene word count must not sit inside the static Requirements block
        assert requirement.index("Write approximately 50 words.") > requirement.index("Respond entirely in")


class TestPrefixAccumulation:
    """Test suite for prefixed_content dependency injection across levels."""

    def _scene_ctx(self, title: str, description: str) -> SceneContext:
        return SceneContext(title=title, description=description, expected_word_count=20)

    async def test_compose_story_injects_prefix_across_scenes(self) -> None:
        role = NovelRole(name="novel_role")
        story = StoryContext(title="St1", description="The departure.")
        scene_1 = self._scene_ctx("S1", "Leaving home.")
        scene_2 = self._scene_ctx("S2", "A stranger appears.")
        story.add_scene_context(scene_1).add_scene_context(scene_2)
        with install_router_usage(
            *return_router_usage(
                "### S1\n\n> Leaving home.\n\nHe left.",
                "### S2\n\n> A stranger appears.\n\nA stranger appeared.",
            )
        ):
            result = await role.compose_story(story)
        assert result is not None
        assert scene_1.prefixed_content == ""
        assert scene_2.prefixed_content == "### S1\n\n> Leaving home.\n\nHe left."

    async def test_compose_chapter_injects_prefix_across_stories(self) -> None:
        role = NovelRole(name="novel_role")
        chapter = ChapterContext(title="Ch1", description="The start.")
        story_a = StoryContext(title="StA", description="A.")
        story_a.add_scene_context(self._scene_ctx("S1", "Leaving home."))
        story_b = StoryContext(title="StB", description="B.")
        story_b.add_scene_context(self._scene_ctx("S2", "A stranger appears."))
        chapter.add_story_context(story_a).add_story_context(story_b)
        with install_router_usage(
            *return_router_usage(
                "### S1\n\n> Leaving home.\n\nAlpha.",
                "### S2\n\n> A stranger appears.\n\nBeta.",
            )
        ):
            result = await role.compose_chapter(chapter)
        assert result is not None
        story_a_block = "## StA\n\n> A.\n\n### S1\n\n> Leaving home.\n\nAlpha."
        assert story_a.prefixed_content == ""
        assert story_b.prefixed_content == story_a_block
        assert story_b.scene_context[0].prefixed_content == story_a_block

    async def test_compose_novel_injects_prefix_across_chapters_and_stories(self) -> None:
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.title = "The Search"
        ctx.description = "A hero searching."
        ctx.expected_word_count = 80

        def story(title: str, scene_title: str, scene_description: str) -> StoryContext:
            s = StoryContext(title=title, description=scene_description)
            s.add_scene_context(self._scene_ctx(scene_title, scene_description))
            return s

        chapter_1 = ChapterContext(title="Ch1", description="The start.")
        chapter_1.add_story_context(story("StA", "S1", "Leaving home."))
        chapter_1.add_story_context(story("StB", "S2", "A stranger appears."))
        chapter_2 = ChapterContext(title="Ch2", description="The road.")
        chapter_2.add_story_context(story("StC", "S3", "The journey."))
        chapter_2.add_story_context(story("StD", "S4", "The arrival."))
        ctx.add_chapter_context(chapter_1).add_chapter_context(chapter_2)

        meta = NovelPlan(
            title="The Search", description="A hero searching.", expected_word_count=80, series_bible=SeriesBible()
        )
        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                raw_value("### S1\n\n> Leaving home.\n\nA."),
                raw_value("### S2\n\n> A stranger appears.\n\nB."),
                raw_value("### S3\n\n> The journey.\n\nC."),
                raw_value("### S4\n\n> The arrival.\n\nD."),
            )
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        chapter_1_block = (
            "# Ch1\n\n> The start.\n\n"
            "## StA\n\n> Leaving home.\n\n### S1\n\n> Leaving home.\n\nA.\n\n"
            "## StB\n\n> A stranger appears.\n\n### S2\n\n> A stranger appears.\n\nB."
        )
        story_c_block = "## StC\n\n> The journey.\n\n### S3\n\n> The journey.\n\nC."
        assert chapter_1.prefixed_content == ""
        assert chapter_2.prefixed_content == chapter_1_block
        assert chapter_1.story_context[1].prefixed_content == (
            "## StA\n\n> Leaving home.\n\n### S1\n\n> Leaving home.\n\nA."
        )
        assert chapter_2.story_context[0].prefixed_content == chapter_1_block
        assert chapter_2.story_context[1].prefixed_content == f"{chapter_1_block}\n\n{story_c_block}"
        assert chapter_2.story_context[0].scene_context[0].prefixed_content == chapter_1_block
        assert chapter_2.story_context[1].scene_context[0].prefixed_content == f"{chapter_1_block}\n\n{story_c_block}"


class TestNovelPlan:
    """Test suite for progressive planning of an empty context tree."""

    async def test_compose_novel_plans_empty_tree(self) -> None:
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=100,
            series_bible=SeriesBible(),
        )
        chapter_plans_json = [{"title": "Ch1", "description": "The hero sets out.", "expected_word_count": 100}]
        story_plans_json = [{"title": "St1", "description": "The departure.", "expected_word_count": 100}]
        scene_plans_json = [{"title": "S1", "description": "Leaving home.", "expected_word_count": 100}]
        responses = return_mixed_router_usage(
            Value(meta, "model"),
            Value(chapter_plans_json, "json"),
            Value(story_plans_json, "json"),
            Value(scene_plans_json, "json"),
            raw_value("### S1\n\n> Leaving home.\n\nHe left."),
        )
        with install_router_usage(*responses):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.title == "The Search"
        assert len(novel.chapter) == 1
        assert novel.chapter[0].title == "Ch1"
        assert novel.chapter[0].story[0].scenes[0].content == "He left."
        assert ctx.novel_plan is not None
        assert ctx.novel_plan.title == "The Search"
        assert ctx.chapter_context[0].chapter_plan is not None
        assert ctx.chapter_context[0].chapter_plan.title == "Ch1"
        assert ctx.chapter_context[0].story_context[0].story_plan is not None
        assert ctx.chapter_context[0].story_context[0].story_plan.title == "St1"
        assert ctx.chapter_context[0].story_context[0].scene_context[0].scene_plan is not None
        assert ctx.chapter_context[0].story_context[0].scene_context[0].scene_plan.title == "S1"
        assert ctx.chapter_context[0].story_context[0].scene_context[0].language == "English"

    async def test_compose_novel_returns_none_when_plan_fails(self) -> None:
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero.", language="English")
        meta = NovelPlan(title="T", description="D", expected_word_count=10, series_bible=SeriesBible())
        with install_router_usage(
            *return_model_json_router_usage(meta)[:1], "not valid json", "still not json", "nope"
        ):
            novel = await role.compose_novel(ctx)
        assert novel is None

    async def test_compose_novel_expands_stories_for_prefilled_chapter(self) -> None:
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.add_chapter_context(ChapterContext(title="Ch1", description="The hero sets out.").set_language("English"))

        meta = NovelPlan(
            title="The Search",
            description="A hero searching.",
            expected_word_count=100,
            series_bible=SeriesBible(),
        )
        story_plans_json = [{"title": "St1", "description": "The departure.", "expected_word_count": 100}]
        scene_plans_json = [{"title": "S1", "description": "Leaving home.", "expected_word_count": 100}]

        responses = return_mixed_router_usage(
            Value(meta, "model"),
            Value(story_plans_json, "json"),
            Value(scene_plans_json, "json"),
            raw_value("### S1\n\n> Leaving home.\n\nHe left."),
        )
        with install_router_usage(*responses):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.chapter[0].story[0].scenes[0].content == "He left."
        assert len(ctx.chapter_context) == 1
        assert len(ctx.chapter_context[0].story_context) == 1
        assert ctx.chapter_context[0].story_context[0].story_plan is not None
        assert ctx.chapter_context[0].story_context[0].story_plan.title == "St1"
        assert ctx.chapter_context[0].story_context[0].scene_context[0].scene_plan is not None
        assert ctx.chapter_context[0].story_context[0].scene_context[0].scene_plan.title == "S1"
        assert ctx.chapter_context[0].story_context[0].scene_context[0].language == "English"


class TestNovelEpub:
    """Test suite for Novel.dump_epub."""

    def test_dump_epub_builds_valid_structure(self, tmp_path: Path) -> None:
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


class RAGRole(LLMTestRole, NovelCompose, RAGCompose):
    """Test role combining mock LLM with RAG-extended novel composition."""


class TestRAGCompose:
    """Test suite for writing style RAG scene prompts."""

    async def test_prepare_scene_requirement_injects_style_digest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        role = RAGRole(name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights the dragon.", expected_word_count=50)
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose with terse action lines.")

        async def fake_fetch(query: str, config: object | None = None) -> List[WritingStyleDocument]:
            return [doc]

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        with install_router_usage(
            *return_router_usage(
                code_block('["hero fights dragon"]'),
                generic_block("Use dark gothic prose with terse action lines.", "String"),
            )
        ):
            requirement = await role.prepare_scene_requirement(ctx)

        assert "## Writing Style Guideline" in requirement
        assert "Use dark gothic prose with terse action lines." in requirement
        assert "## Writing Style References" not in requirement

    async def test_prepare_scene_requirement_skips_digest_when_digest_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        role = RAGRole(name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights the dragon.", expected_word_count=50)
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose with terse action lines.")

        async def fake_fetch(query: str, config: object | None = None) -> List[WritingStyleDocument]:
            return [doc]

        async def fake_digest(prompt: str, **kwargs: object) -> str | None:
            return None

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        monkeypatch.setattr(RAGRole, "ageneric_string", staticmethod(fake_digest))
        with install_router_usage(*return_json_router_usage('["hero fights dragon"]')):
            requirement = await role.prepare_scene_requirement(ctx)

        assert "## Writing Style Guideline" not in requirement
        assert "The hero fights the dragon." in requirement

    async def test_prepare_scene_requirement_without_docs_keeps_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        role = RAGRole(name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)

        async def fake_fetch(query: str, config: object | None = None) -> List[WritingStyleDocument]:
            return []

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        with install_router_usage(*return_json_router_usage('["hero fights"]')):
            requirement = await role.prepare_scene_requirement(ctx)

        assert "## Writing Style Guideline" not in requirement
        assert "The hero fights." in requirement

    async def test_fetch_style_docs_uses_custom_query_and_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        role = RAGRole(name="rag_role", rag_query="中文查询指南", rag_limit=7)
        ctx = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)
        captured_queries: List[str] = []
        captured_configs: List[WritingStyleFetchConfig] = []

        async def fake_refine(question: str, **kwargs: object) -> List[str]:
            captured_queries.append(question)
            return ["查询一", "查询二"]

        async def fake_fetch(
            query: object, config: WritingStyleFetchConfig | None = None
        ) -> List[WritingStyleDocument]:
            if config is not None:
                captured_configs.append(config)
            return []

        monkeypatch.setattr(RAGRole, "arefined_query", staticmethod(fake_refine))
        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))

        docs = await role._fetch_style_docs(ctx)

        assert docs == []
        assert captured_queries == ["中文查询指南"]
        assert captured_configs
        assert captured_configs[0].limit == 7

    async def test_fetch_style_docs_defaults_to_scene_description(self, monkeypatch: pytest.MonkeyPatch) -> None:
        role = RAGRole(name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)
        captured_queries: List[str] = []

        async def fake_refine(question: str, **kwargs: object) -> List[str]:
            captured_queries.append(question)
            return ["hero fights"]

        async def fake_fetch(
            query: object, config: WritingStyleFetchConfig | None = None
        ) -> List[WritingStyleDocument]:
            return []

        monkeypatch.setattr(RAGRole, "arefined_query", staticmethod(fake_refine))
        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))

        await role._fetch_style_docs(ctx)

        assert captured_queries == ["The hero fights."]

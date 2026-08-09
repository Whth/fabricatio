"""Test module for fabricatio-novel contexts, models, and generation capabilities."""

from pathlib import Path
from typing import List

import pytest
from fabricatio_character.models.character import CharacterCard, CharacterCardDiff
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_json_router_usage, return_model_json_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.capabilities.rag import RAGCompose
from fabricatio_novel.models.context.base import CharactorTrace
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.novel import Novel, NovelMetadata
from fabricatio_novel.models.plan import ChapterPlan, NovelPlan, ScenePlan, StoryPlan
from fabricatio_novel.models.rag import WritingStyleDocument, WritingStyleFetchConfig
from fabricatio_novel.models.scene import Scene
from fabricatio_novel.models.series_book import SeriesBible


def card(name: str = "Hero", look: str = "tall") -> CharacterCard:
    return CharacterCard(name=name, role="protagonist", look=look, act="brave", want="seek truth", flaw="stubborn")


class TestNovelContext:
    """Test suite for NovelContext."""

    def test_create_detects_language(self) -> None:
        ctx = NovelContext.create("少年踏上旅途。")
        assert ctx.language == "简体中文"
        assert ctx.outline == "少年踏上旅途。"
        assert ctx.title == ""
        assert ctx.description == ""
        assert isinstance(ctx.series_bible, SeriesBible)
        assert ctx.chapter_context == []

    def test_create_with_explicit_language(self) -> None:
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        assert ctx.language == "English"


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


class TestNovelCompose:
    """Test suite for the generation chain with mock LLM."""

    async def test_compose_scene_writes_content_back_to_context(self) -> None:
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="Departure", description="The hero leaves home.", expected_word_count=50)
        expected = Scene(
            title="Departure", description="The hero leaves home.", expected_word_count=50, content="He walked out."
        )
        with install_router_usage(*return_model_json_router_usage(expected)):
            scene = await role.compose_scene(ctx)
        assert scene is not None
        assert scene.content == "He walked out."
        assert ctx.content == "He walked out."

    async def test_compose_scene_evolves_charactor_trace(self) -> None:
        role = NovelRole(name="novel_role")
        trace = CharactorTrace(start=card(), end=card())
        ctx = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)
        ctx.charactor_trace.append(trace)
        expected_scene = Scene(
            title="Battle", description="The hero fights.", expected_word_count=50, content="He fought."
        )
        expected_diff = CharacterCardDiff(look="scarred")
        with install_router_usage(*return_model_json_router_usage(expected_scene, expected_diff)):
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

        meta = NovelMetadata(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=40,
            series_bible=SeriesBible(),
        )
        expected_scene_1 = Scene(title="S1", description="Leaving home.", expected_word_count=20, content="He left.")
        expected_scene_2 = Scene(
            title="S2", description="A stranger appears.", expected_word_count=20, content="A stranger appeared."
        )

        with install_router_usage(*return_model_json_router_usage(meta, expected_scene_1, expected_scene_2)):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.title == "The Search"
        assert len(novel.chapter) == 1
        assert len(novel.chapter[0].story) == 1
        assert len(novel.chapter[0].story[0].scenes) == 2
        assert novel.chapter[0].story[0].scenes[1].content == "A stranger appeared."
        assert ctx.title == "The Search"
        assert ctx.chapter_context[0].story_context[0].scene_context[1].content == "A stranger appeared."
        assert ctx.chapter_context[0].story_context[0].scene_context[1].previous_content == "He left."
        assert ctx.chapter_context[0].story_context[0].scene_context[0].previous_content == ""

    async def test_compose_novel_returns_none_when_metadata_fails(self) -> None:
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero.", language="English")
        with install_router_usage("not valid json", "", ""):
            novel = await role.compose_novel(ctx)
        assert novel is None

    async def test_prepare_scene_requirement_renders_previous_content_after_static_head(self) -> None:
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.previous_content = "He walked into the dark."

        requirement = await role.prepare_scene_requirement(ctx)

        # the static head (incl. per-run language) leads so it stays prefix-cacheable
        assert requirement.startswith("# Scene Writing")
        assert requirement.index("Respond entirely in") < requirement.index("# Previous Content")
        assert requirement.index("He walked into the dark.") > requirement.index("# Previous Content")
        assert requirement.index("A stranger appears.") > requirement.index("## Scene")
        # the per-scene word count must not sit inside the static Requirements block
        assert requirement.index("Write approximately 50 words.") > requirement.index("Respond entirely in")


class TestNovelPlan:
    """Test suite for planning an empty context tree."""

    async def test_compose_novel_plans_empty_tree(self) -> None:
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        meta = NovelMetadata(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=100,
            series_bible=SeriesBible(),
        )
        plan = NovelPlan(
            chapters=[
                ChapterPlan(
                    title="Ch1",
                    description="The hero sets out.",
                    expected_word_count=100,
                    stories=[
                        StoryPlan(
                            title="St1",
                            description="The departure.",
                            expected_word_count=100,
                            scenes=[ScenePlan(title="S1", description="Leaving home.", expected_word_count=100)],
                        )
                    ],
                )
            ]
        )
        expected_scene = Scene(title="S1", description="Leaving home.", expected_word_count=100, content="He left.")
        with install_router_usage(*return_model_json_router_usage(meta, plan, expected_scene)):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.title == "The Search"
        assert len(novel.chapter) == 1
        assert novel.chapter[0].title == "Ch1"
        assert novel.chapter[0].story[0].scenes[0].content == "He left."
        assert ctx.chapter_context[0].story_context[0].scene_context[0].language == "English"

    async def test_compose_novel_returns_none_when_plan_fails(self) -> None:
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero.", language="English")
        meta = NovelMetadata(title="T", description="D", expected_word_count=10, series_bible=SeriesBible())
        with install_router_usage(
            *return_model_json_router_usage(meta)[:1], "not valid json", "still not json", "nope"
        ):
            novel = await role.compose_novel(ctx)
        assert novel is None


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
        path = novel.dump_epub(tmp_path / "novel.epub", language="English", font=font_file, cover=cover_file)
        assert path.exists()
        assert path.stat().st_size > 0

        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            assert names[0] == "mimetype", f"mimetype must be the first entry, got {names[:3]}"
            assert zf.read("mimetype") == b"application/epub+zip"
            assert "META-INF/container.xml" in names
            opf = next(n for n in names if n.endswith("content.opf"))
            assert "<dc:language>en</dc:language>" in zf.read(opf).decode("utf-8")
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

    async def test_prepare_scene_requirement_injects_style_docs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        role = RAGRole(name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights the dragon.", expected_word_count=50)
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose with terse action lines.")

        async def fake_fetch(query: str, config: object | None = None) -> List[WritingStyleDocument]:
            return [doc]

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        with install_router_usage(*return_json_router_usage('["hero fights dragon"]')):
            requirement = await role.prepare_scene_requirement(ctx)

        assert "## Writing Style References" in requirement
        assert "Dark gothic prose with terse action lines." in requirement

    async def test_prepare_scene_requirement_without_docs_keeps_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        role = RAGRole(name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)

        async def fake_fetch(query: str, config: object | None = None) -> List[WritingStyleDocument]:
            return []

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        with install_router_usage(*return_json_router_usage('["hero fights"]')):
            requirement = await role.prepare_scene_requirement(ctx)

        assert "## Writing Style References" not in requirement
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

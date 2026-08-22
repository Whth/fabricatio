"""Writing-style RAG tests for fabricatio-novel."""

from itertools import pairwise
from typing import List

import pytest
from _support import RAGRole, prefix_log
from fabricatio_mock.models.mock_router import return_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.models.context.rag import RagRetrieval
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import ScenePlan, ScenePlans
from fabricatio_novel.models.rag import WritingStyleDocument, WritingStyleFetchConfig
from fabricatio_novel.models.series_book import SeriesBible


class TestRAGCompose:
    """Test suite for writing style RAG scene prompts."""

    async def test_prepare_scene_requirement_injects_style_docs_in_order(self) -> None:
        """Assert raw style docs render between the before-story prefix and the story so far."""
        role = RAGRole(name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights the dragon.", expected_word_count=50)
        ctx.set_prefix_log(prefix_log("Chapter One\n\nThe hero leaves home.", title="Battle"))
        ctx.set_scenes_log(prefix_log("Scene one: the hero rides north.", title="Scene one"))
        ctx.set_writing_styles(["Dark gothic prose with terse action lines."])

        requirement = await role.prepare_scene_requirement(ctx)

        assert "## Writing Styles" in requirement
        assert "Dark gothic prose with terse action lines." in requirement
        assert requirement.index("# Previous Content") < requirement.index("## Writing Styles")
        assert requirement.index("## Writing Styles") < requirement.index("## Story so far")
        assert "## Writing Style Guideline" not in requirement

    async def test_compose_story_keeps_stable_prefix_byte_identical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert scene prompts share a byte-identical stable region so prefix caching holds.

        Scene k+1's prompt must have scene k's prompt as a byte prefix through
        the whole of scene k's composed content; only the newly written scene
        and the scene instruction may differ.
        """
        role = RAGRole(name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        bible = SeriesBible(characters=["Hero", "Villain"], background_settings=["The world is cold."])
        story.set_series_bible(bible)
        for title, desc in [("S1", "Leaving home."), ("S2", "A stranger appears."), ("S3", "The road.")]:
            story.add_scene_context(
                SceneContext(title=title, description=desc, expected_word_count=50)
                .set_writing_styles(["Dark gothic prose with terse action lines."])
                .set_series_bible(bible)
            )

        async def fake_fetch(query: object, config: object | None = None) -> List[WritingStyleDocument]:
            return []

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        with install_router_usage(*return_router_usage("One.", "Two.", "Three.")):
            result = await role.compose_story(story)

        assert result is not None
        reqs = [await role.prepare_scene_requirement(scene) for scene in story.scene_context]

        stable = reqs[1][: reqs[1].index("## Story so far")]
        assert reqs[0][: reqs[0].index("## Scene")] == stable
        assert reqs[2][: reqs[2].index("## Story so far")] == stable
        assert "Dark gothic prose with terse action lines." in stable
        assert "The world is cold." in stable

        for prev, nxt in pairwise(reqs):
            if "--- End of Story so far ---" in prev:
                shared = prev.index("\n--- End of Story so far ---")
                assert nxt.startswith(prev[:shared])

    async def test_prepare_story_retrieves_docs_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert plan_scenes_phase retrieves style docs exactly once."""
        role = RAGRole(name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        story.set_rag(RagRetrieval())
        story.scene_context.append(SceneContext(title="S1", description="Leaving home.", expected_word_count=50))
        fetched: List[object] = []
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")

        async def fake_fetch(query: object, config: object | None = None) -> List[WritingStyleDocument]:
            fetched.append(query)
            return [doc]

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))

        async def fake_propose(model: object, requirement: object, **kwargs: object) -> object:
            return []

        monkeypatch.setattr(RAGRole, "propose", staticmethod(fake_propose))

        await role.plan_scenes_phase(story)

        assert fetched == [["The departure."]]

    async def test_prepare_story_without_docs_keeps_requirement_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert a story without retrieved style docs renders no references section."""
        role = RAGRole(name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        scene = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)
        story.scene_context.append(scene)
        story.set_rag(RagRetrieval())

        async def fake_fetch_docs(ctx: StoryContext, **kwargs: object) -> List[WritingStyleDocument]:
            return []

        monkeypatch.setattr(RAGRole, "_fetch_style_docs", staticmethod(fake_fetch_docs))

        await role.prepare_story(story)

        assert story.writing_styles == []
        requirement = await role.prepare_scene_requirement(scene)
        assert "## Writing Styles" not in requirement
        assert "The hero fights." in requirement

    async def test_plan_scenes_propagates_style_docs_to_scenes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert scenes materialized after the story prep inherit the story's style references."""
        role = RAGRole(name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        story.set_writing_styles(["Dark gothic prose with terse action lines."])

        async def fake_fetch_docs(ctx: StoryContext, **kwargs: object) -> List[WritingStyleDocument]:
            return []

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> ScenePlans:
            return ScenePlans(root=[ScenePlan(title="S1", description="Leaving home.", weight=1.0)])

        monkeypatch.setattr(RAGRole, "_fetch_style_docs", staticmethod(fake_fetch_docs))
        monkeypatch.setattr(RAGRole, "propose", staticmethod(fake_propose))

        await role.plan_scenes_phase(story)

        assert len(story.scene_context) == 1
        assert story.scene_context[0].writing_styles == story.writing_styles

    async def test_plan_scenes_injects_held_style_docs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert the story's held style references render into the scene planning prompt."""
        role = RAGRole(name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        story.set_writing_styles(["Dark gothic prose with terse action lines."])
        captured: List[str] = []

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> None:
            captured.append(requirement)

        monkeypatch.setattr(RAGRole, "propose", staticmethod(fake_propose))

        await role.plan_scenes(story)

        assert captured
        assert "- Writing styles:" in captured[0]
        assert "Dark gothic prose with terse action lines." in captured[0]

    async def test_fetch_style_docs_combines_query_and_applies_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert _fetch_style_docs joins description and rag_query and applies the limit."""
        role = RAGRole(name="rag_role")
        ctx = StoryContext(title="Battle", description="The hero fights.")
        ctx.set_rag(RagRetrieval(query="中文查询指南", limit=7))
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")
        captured_queries: List[object] = []
        captured_configs: List[WritingStyleFetchConfig] = []

        async def fake_fetch(
            query: object, config: WritingStyleFetchConfig | None = None
        ) -> List[WritingStyleDocument]:
            captured_queries.append(query)
            if config is not None:
                captured_configs.append(config)
            return [doc] * 8

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))

        docs = await role._fetch_style_docs(ctx)

        assert docs == [doc] * 7
        assert captured_queries == [["The hero fights.\n中文查询指南"]]
        assert captured_configs
        assert captured_configs[0].limit == 7

    async def test_fetch_style_docs_defaults_to_story_description(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert _fetch_style_docs uses the story description when no rag_query is set."""
        role = RAGRole(name="rag_role")
        ctx = StoryContext(title="Battle", description="The hero fights.")
        ctx.set_rag(RagRetrieval())
        captured_queries: List[object] = []

        async def fake_fetch(
            query: object, config: WritingStyleFetchConfig | None = None
        ) -> List[WritingStyleDocument]:
            captured_queries.append(query)
            return []

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))

        await role._fetch_style_docs(ctx)

        assert captured_queries == [["The hero fights."]]

    async def test_fetch_style_docs_skips_blank_prompt_docs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert docs whose prompt renders blank are filtered out."""
        role = RAGRole(name="rag_role")
        ctx = StoryContext(title="Battle", description="The hero fights.")
        ctx.set_rag(RagRetrieval())
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")
        blank = WritingStyleDocument.with_text_chunk("   ")

        async def fake_fetch(
            query: object, config: WritingStyleFetchConfig | None = None
        ) -> List[WritingStyleDocument]:
            return [blank, doc, blank]

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))

        docs = await role._fetch_style_docs(ctx)

        assert docs == [doc]

    async def test_rag_settings_survive_story_composition(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert retrieval settings set on the story survive composition and scenes stay RAG-free."""
        role = RAGRole(name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        story.set_rag(RagRetrieval(query="guide", limit=7))

        async def fake_fetch(
            query: object, config: WritingStyleFetchConfig | None = None
        ) -> List[WritingStyleDocument]:
            return []

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        with install_router_usage(
            *return_router_usage('[{"title": "S1", "description": "Leaving home.", "weight": 1.0}]', "He left.")
        ):
            result = await role.compose_story(story)

        assert result is not None
        assert story.rag == RagRetrieval(query="guide", limit=7)
        assert story.scene_context[0].writing_styles == []

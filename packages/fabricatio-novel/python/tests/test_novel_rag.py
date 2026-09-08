"""Writing-style RAG tests for fabricatio-novel."""

from itertools import pairwise

import pytest
from _support import RAGRole, prefix_log
from fabricatio_mock.models.mock_router import (
    Value,
    return_generic_router_usage,
    return_mixed_router_usage,
)
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.log import ContextEntry, ContextLog
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.rag import RagRetrieval, RagStoryContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import ScenePlan, ScenePlans
from fabricatio_novel.models.rag import WritingStyleDocument, WritingStyleFetchConfig
from fabricatio_novel.models.series_book import SeriesBible


class TestRAGCompose:
    """Test suite for writing style RAG scene prompts."""

    async def test_prepare_scene_requirement_injects_style_docs_in_order(self) -> None:
        """Assert raw style docs render after the leading novel-so-far block."""
        role = RAGRole(name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights the dragon.", expected_word_count=50)
        ctx.set_prefix_log(
            prefix_log("Chapter One\n\nThe hero leaves home.\n\nScene one: the hero rides north.", title="Battle")
        )
        ctx.set_writing_styles(["Dark gothic prose with terse action lines."])

        requirement = await role.prepare_scene_requirement(ctx)

        assert "## Writing Styles" in requirement
        assert "Dark gothic prose with terse action lines." in requirement
        assert requirement.index("--- End of Novel so far ---") < requirement.index("## Writing Styles")
        assert "## Writing Style Guideline" not in requirement

    async def test_compose_story_keeps_stable_prefix_byte_identical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert scene prompts share a byte-identical stable region so prefix caching holds.

        Scene k+1's prompt must have scene k's prompt as a byte prefix through
        the whole of scene k's composed content; only the newly written scene
        and the scene instruction may differ.
        """
        role = RAGRole(name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        # the bible reaches stories as a seeded prefix entry, never as a held model
        seed = ContextEntry(
            kind="setting_bible",
            title="Setting Bible",
            body=SeriesBible(characters=["Hero", "Villain"], background_settings=["The world is cold."])
            .as_prompt()
            .strip(),
        )
        story.set_prefix_log(ContextLog(entries=(seed,)))
        for title, desc in [("S1", "Leaving home."), ("S2", "A stranger appears."), ("S3", "The road.")]:
            story.add_context(
                SceneContext(title=title, description=desc, expected_word_count=50).set_writing_styles(
                    ["Dark gothic prose with terse action lines."],
                ),
            )

        async def fake_fetch(query: object, config: object | None = None) -> list[WritingStyleDocument]:
            return []

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        with install_router_usage(*return_generic_router_usage("One.", "Two.", "Three.")):
            result = await role.compose_story(story)

        assert result is not None
        reqs = [await role.prepare_scene_requirement(scene) for scene in story.child_contexts]

        assert reqs[0].startswith("--- Start of Novel so far ---")
        assert "Dark gothic prose with terse action lines." in reqs[0]
        assert "The world is cold." in reqs[0]

        # each later prompt shares every byte of the earlier prompt's novel-so-far bodies
        for prev, nxt in pairwise(reqs):
            cut = prev.rindex("\n--- End of Novel so far ---")
            assert nxt.startswith(prev[:cut])

    async def test_prepare_story_retrieves_docs_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert plan_scenes_phase retrieves style docs exactly once."""
        role = RAGRole(name="rag_role")
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval())
        story.child_contexts.append(SceneContext(title="S1", description="Leaving home.", expected_word_count=50))
        fetched: list[object] = []
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")

        async def fake_fetch(query: object, config: object | None = None) -> list[WritingStyleDocument]:
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
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval())
        scene = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)
        story.child_contexts.append(scene)

        async def fake_fetch_docs(ctx: StoryContext, **kwargs: object) -> list[WritingStyleDocument]:
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
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval())
        story.set_writing_styles(["Dark gothic prose with terse action lines."])

        async def fake_fetch_docs(ctx: RagStoryContext) -> list[WritingStyleDocument]:
            return []

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> ScenePlans:
            return ScenePlans(
                root=[
                    ScenePlan(
                        title="S1", description="Leaving home.", weight=1.0, writing_styles=[], writing_constraints=[]
                    )
                ]
            )

        monkeypatch.setattr(RAGRole, "_fetch_style_docs", staticmethod(fake_fetch_docs))
        monkeypatch.setattr(RAGRole, "propose", staticmethod(fake_propose))

        await role.plan_scenes_phase(story)

        assert len(story.child_contexts) == 1
        assert story.child_contexts[0].writing_styles == story.writing_styles

    async def test_plan_scenes_injects_held_style_docs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert the story's held style references render into the scene planning prompt."""
        role = RAGRole(name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        story.set_writing_styles(["Dark gothic prose with terse action lines."])
        captured: list[str] = []

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
        ctx = RagStoryContext(
            title="Battle", description="The hero fights.", rag=RagRetrieval(query="中文查询指南", limit=7)
        )
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")
        captured_queries: list[object] = []
        captured_configs: list[WritingStyleFetchConfig] = []

        async def fake_fetch(
            query: object,
            config: WritingStyleFetchConfig | None = None,
        ) -> list[WritingStyleDocument]:
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
        ctx = RagStoryContext(title="Battle", description="The hero fights.", rag=RagRetrieval())
        captured_queries: list[object] = []

        async def fake_fetch(
            query: object,
            config: WritingStyleFetchConfig | None = None,
        ) -> list[WritingStyleDocument]:
            captured_queries.append(query)
            return []

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))

        await role._fetch_style_docs(ctx)

        assert captured_queries == [["The hero fights."]]

    async def test_fetch_style_docs_skips_blank_prompt_docs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert docs whose prompt renders blank are filtered out."""
        role = RAGRole(name="rag_role")
        ctx = RagStoryContext(title="Battle", description="The hero fights.", rag=RagRetrieval())
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")
        blank = WritingStyleDocument.with_text_chunk("   ")

        async def fake_fetch(
            query: object,
            config: WritingStyleFetchConfig | None = None,
        ) -> list[WritingStyleDocument]:
            return [blank, doc, blank]

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))

        docs = await role._fetch_style_docs(ctx)

        assert docs == [doc]

    async def test_rag_settings_survive_story_composition(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert retrieval settings set on the story survive composition and scenes stay RAG-free."""
        role = RAGRole(name="rag_role")
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval(query="guide", limit=7))

        async def fake_fetch(
            query: object,
            config: WritingStyleFetchConfig | None = None,
        ) -> list[WritingStyleDocument]:
            return []

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        with install_router_usage(
            *return_mixed_router_usage(
                Value(
                    [
                        {
                            "title": "S1",
                            "description": "Leaving home.",
                            "weight": 1.0,
                            "writing_styles": [],
                            "writing_constraints": [],
                        }
                    ],
                    "json",
                ),
                Value("He left.", "generic"),
            ),
        ):
            result = await role.compose_story(story)

        assert result is not None
        assert story.rag == RagRetrieval(query="guide", limit=7)
        assert story.child_contexts[0].writing_styles == []

    async def test_plan_stories_phase_seals_and_is_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert the RAG story-planning phase seals plain stories and leaves sealed ones untouched."""
        from fabricatio_novel.actions.novel import RagPlanStoriesStage
        from fabricatio_novel.capabilities.chapter import ChapterCompose

        async def fake_plan(self: ChapterCompose, ctx: ChapterContext, send_to: str | None = None) -> bool:
            return True

        monkeypatch.setattr(ChapterCompose, "plan_stories_phase", fake_plan)
        stage = RagPlanStoriesStage(rag_query="guide", rag_limit=3)
        chapter = ChapterContext(title="Ch1", description="The start.", expected_word_count=100)
        chapter.add_context(StoryContext(title="St1", description="The departure.", expected_word_count=100))
        chapter.add_context(RagStoryContext(title="St2", description="The return.", rag=RagRetrieval()))

        assert await stage.plan_stories_phase(chapter) is True

        sealed = chapter.child_contexts[0]
        assert isinstance(sealed, RagStoryContext)
        assert sealed.rag == RagRetrieval(query="guide", limit=3)
        assert sealed.title == "St1"
        assert chapter.child_contexts[1].rag == RagRetrieval()

        await RagPlanStoriesStage(rag_query="other").plan_stories_phase(chapter)
        assert chapter.child_contexts[0].rag == RagRetrieval(query="guide", limit=3)
        assert chapter.child_contexts[1].rag == RagRetrieval()

    async def test_rag_plan_stage_seals_stories_from_task_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert RagPlanStoriesStage seals each chapter's stories with the context-overridden settings."""
        from fabricatio_novel.actions.novel import RagPlanStoriesStage
        from fabricatio_novel.capabilities.chapter import ChapterCompose

        async def fake_plan(self: ChapterCompose, ctx: ChapterContext, send_to: str | None = None) -> bool:
            return True

        monkeypatch.setattr(ChapterCompose, "plan_stories_phase", fake_plan)
        stage = RagPlanStoriesStage(rag_query="guide", rag_limit=3)
        novel = NovelContext.create("The hero seeks his father.", language="English")
        chapter = ChapterContext(title="Ch1", description="The start.", expected_word_count=100)
        chapter.add_context(StoryContext(title="St1", description="The departure.", expected_word_count=100))
        novel.add_context(chapter)

        assert await stage._execute(novel) is True
        sealed = chapter.child_contexts[0]
        assert isinstance(sealed, RagStoryContext)
        assert sealed.rag == RagRetrieval(query="guide", limit=3)

"""Writing-style RAG tests for fabricatio-novel."""

from itertools import pairwise
from pathlib import Path

import pytest
from _support import card, prefix_log
from fabricatio_character.models.character import CharacterSpan
from fabricatio_mock import MockScript, Value, make_test_role
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.capabilities.rag import RAGChapterCompose, RAGNovelCompose
from fabricatio_novel.models.context.chapter import ChapterContext, RagChapterContext
from fabricatio_novel.models.context.log import ContextEntry, ContextLog
from fabricatio_novel.models.context.novel import NovelContext, RagNovelContext
from fabricatio_novel.models.context.rag import RagRetrieval, RagStoryContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import ChapterPlan, ScenePlan, ScenePlans, StoryPlan
from fabricatio_novel.models.rag import WritingStyleDocument, WritingStyleFetchConfig
from fabricatio_novel.models.series_book import SeriesBible


class TestRAGChapterCompose:
    """Test suite for writing style RAG scene prompts."""

    async def test_prepare_scene_requirement_injects_style_docs_in_order(self) -> None:
        """Assert raw style docs render after the leading novel-so-far block."""
        role = make_test_role(NovelCompose, RAGChapterCompose, name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights the dragon.", expected_word_count=50)
        ctx.set_prefix_log(
            prefix_log("Chapter One\n\nThe hero leaves home.\n\nScene one: the hero rides north.", title="Battle")
        )
        ctx.set_writing_styles(["Dark gothic prose with terse action lines."])

        requirement = await role.prepare_scene_requirement(ctx)

        assert "### Writing styles" in requirement
        assert "Dark gothic prose with terse action lines." in requirement
        assert requirement.index("--- End of Novel so far ---") < requirement.index("### Writing styles")
        assert "## Writing Style Guideline" not in requirement

    async def test_compose_story_keeps_stable_prefix_byte_identical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert scene prompts share a byte-identical stable region so prefix caching holds.

        Scene k+1's prompt must have scene k's prompt as a byte prefix through
        the whole of scene k's composed content; only the newly written scene
        and the scene instruction may differ.
        """
        role = make_test_role(NovelCompose, RAGChapterCompose, name="rag_role")
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval())
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

        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")

        async def fake_fetch(query: object, config: object | None = None) -> list[WritingStyleDocument]:
            return [doc]

        async def fake_refine(question: object, **kwargs: object) -> list[str]:
            return ["the departure", "a cold platform"]

        monkeypatch.setattr(type(role), "afetch_document", staticmethod(fake_fetch))
        monkeypatch.setattr(type(role), "arefined_query", staticmethod(fake_refine))
        with MockScript.from_values(
            Value.from_generic("One.", name="scene 1 prose"),
            Value.from_generic("Two.", name="scene 2 prose"),
            Value.from_generic("Three.", name="scene 3 prose"),
        ):
            result = await role.compose_story(story)

        assert result is not None
        reqs = [await role.prepare_scene_requirement(scene) for scene in story.child_contexts]

        assert reqs[0].startswith("--- Start of Novel so far ---")
        assert "Dark gothic prose with terse action lines." in reqs[0]
        assert "The world is cold." in reqs[0]

        for req in reqs:
            assert doc.as_prompt() in req
            assert req.index(doc.as_prompt()) < req.rindex("--- End of Novel so far ---")

        # each later prompt shares every byte of the earlier prompt's novel-so-far bodies
        for prev, nxt in pairwise(reqs):
            cut = prev.rindex("\n--- End of Novel so far ---")
            assert nxt.startswith(prev[:cut])

    async def test_prepare_story_retrieves_docs_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert plan_scenes_phase retrieves style docs exactly once."""
        role = make_test_role(NovelCompose, RAGChapterCompose, name="rag_role")
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval())
        story.child_contexts.append(SceneContext(title="S1", description="Leaving home.", expected_word_count=50))
        fetched: list[object] = []
        refined: list[object] = []
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")

        async def fake_fetch(query: object, config: object | None = None) -> list[WritingStyleDocument]:
            fetched.append(query)
            return [doc]

        async def fake_refine(question: object, **kwargs: object) -> list[str]:
            refined.append(question)
            return ["leaving home", "the departure"]

        monkeypatch.setattr(type(role), "afetch_document", staticmethod(fake_fetch))
        monkeypatch.setattr(type(role), "arefined_query", staticmethod(fake_refine))

        async def fake_propose(model: object, requirement: object, **kwargs: object) -> object:
            return []

        monkeypatch.setattr(type(role), "propose", staticmethod(fake_propose))

        await role.plan_scenes_phase(story)

        assert refined == ["The departure."]
        assert fetched == [["leaving home", "the departure"]]

    async def test_prepare_story_without_docs_keeps_requirement_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert a story without retrieved style docs renders no references section."""
        role = make_test_role(NovelCompose, RAGChapterCompose, name="rag_role")
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval())
        scene = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)
        story.child_contexts.append(scene)

        async def fake_fetch_docs(
            source: str, rag: RagRetrieval, label: str, **kwargs: object
        ) -> list[WritingStyleDocument]:
            return []

        monkeypatch.setattr(type(role), "_fetch_style_docs", staticmethod(fake_fetch_docs))

        await role.prepare_story(story)

        assert story.writing_styles == []
        requirement = await role.prepare_scene_requirement(scene)
        assert "## Writing Styles" not in requirement
        assert "The hero fights." in requirement

    async def test_prepare_story_stores_docs_as_retrieved_styles(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert prepare_story holds retrieved docs on retrieved_styles, leaving planned styles untouched."""
        role = make_test_role(NovelCompose, RAGChapterCompose, name="rag_role")
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval())
        docs = [
            WritingStyleDocument.with_text_chunk("Dark gothic prose."),
            WritingStyleDocument.with_text_chunk("Terse dialogue."),
        ]

        async def fake_fetch_docs(
            source: str, rag: RagRetrieval, label: str, **kwargs: object
        ) -> list[WritingStyleDocument]:
            return docs

        monkeypatch.setattr(type(role), "_fetch_style_docs", staticmethod(fake_fetch_docs))

        await role.prepare_story(story)

        assert story.retrieved_styles == [doc.as_prompt() for doc in docs]
        assert story.writing_styles == []

    async def test_retrieved_docs_seed_every_scene_prefix_once(self) -> None:
        """Assert each scene's prefix holds exactly one shared style_references entry, idempotently."""
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval())
        story.add_retrieved_styles(["Dark gothic prose with terse action lines."])
        story.add_context(
            SceneContext(title="S1", description="Leaving home.", expected_word_count=50).set_content("He left.")
        )
        story.add_context(SceneContext(title="S2", description="The road.", expected_word_count=50))

        for _ in range(2):
            scenes = list(story.iter_prefixed_contexts())

        assert [entry.kind for entry in scenes[0].prefix_log.entries] == ["style_references"]
        assert [entry.kind for entry in scenes[1].prefix_log.entries] == ["style_references", "scene_content"]
        for scene in scenes:
            assert "Dark gothic prose with terse action lines." in scene.prefix_log.render()

    async def test_next_story_prefix_excludes_previous_story_docs(self) -> None:
        """Assert a story's retrieved docs never reach the next story's or its scenes' prefixes."""
        chapter = RagChapterContext(title="Ch1", description="A framing chapter.", expected_word_count=100)
        story_a = RagStoryContext(title="StA", description="The departure.", rag=RagRetrieval())
        story_a.add_retrieved_styles(["Style A."])
        story_a.add_context(
            SceneContext(title="SA1", description="Leaving.", expected_word_count=50).set_content("He left.")
        )
        story_a.add_context(SceneContext(title="SA2", description="The road.", expected_word_count=50))
        story_b = RagStoryContext(title="StB", description="The return.", rag=RagRetrieval())
        story_b.add_retrieved_styles(["Style B."])
        story_b.add_context(SceneContext(title="SB1", description="Arriving.", expected_word_count=50))
        chapter.add_context(story_a)
        chapter.add_context(story_b)

        stories = list(chapter.iter_prefixed_contexts())
        scenes = [list(story.iter_prefixed_contexts()) for story in stories]

        assert [entry.kind for entry in stories[1].prefix_log.entries] == ["chapter_header", "scene_content"]
        assert "He left." in stories[1].prefix_log.render()
        assert "Style A." not in stories[1].prefix_log.render()
        for scene in scenes[1]:
            refs = [entry for entry in scene.prefix_log.entries if entry.kind == "style_references"]
            assert len(refs) == 1
            assert "Style B." in refs[0].body
            assert "Style A." not in refs[0].body
        refs_a = [entry for entry in scenes[0][0].prefix_log.entries if entry.kind == "style_references"]
        assert len(refs_a) == 1
        assert "Style A." in refs_a[0].body
        assert "Style B." not in refs_a[0].body

    async def test_plan_scenes_keeps_retrieved_docs_off_scenes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert retrieved docs stay on the story; scenes inherit only planned styles."""
        role = make_test_role(NovelCompose, RAGChapterCompose, name="rag_role")
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval())
        story.set_writing_styles(["Dark gothic prose with terse action lines."])
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")

        async def fake_fetch_docs(
            source: str, rag: RagRetrieval, label: str, **kwargs: object
        ) -> list[WritingStyleDocument]:
            return [doc]

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> ScenePlans:
            return ScenePlans(
                root=[
                    ScenePlan(
                        title="S1",
                        description="Leaving home.",
                        weight=1.0,
                        writing_styles=["Close first person."],
                        writing_constraints=[],
                    )
                ]
            )

        monkeypatch.setattr(type(role), "_fetch_style_docs", staticmethod(fake_fetch_docs))
        monkeypatch.setattr(type(role), "propose", staticmethod(fake_propose))

        await role.plan_scenes_phase(story)

        assert story.retrieved_styles == [doc.as_prompt()]
        assert story.child_contexts[0].writing_styles == [
            "Dark gothic prose with terse action lines.",
            "Close first person.",
        ]
        assert doc.as_prompt() not in story.child_contexts[0].writing_styles

    async def test_plan_scenes_injects_held_style_docs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert the story's held style references render into the scene planning prompt."""
        role = make_test_role(NovelCompose, RAGChapterCompose, name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        story.set_writing_styles(["Dark gothic prose with terse action lines."])
        captured: list[str] = []

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> None:
            captured.append(requirement)

        monkeypatch.setattr(type(role), "propose", staticmethod(fake_propose))

        await role.plan_scenes(story)

        assert captured
        assert "### Writing styles" in captured[0]
        assert "Dark gothic prose with terse action lines." in captured[0]

    async def test_fetch_style_docs_combines_query_and_applies_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert _fetch_style_docs joins the level's own text and rag_query, then applies the limit."""
        role = make_test_role(NovelCompose, RAGChapterCompose, name="rag_role")
        ctx = RagStoryContext(
            title="Battle", description="The hero fights.", rag=RagRetrieval(query="query guide", limit=7)
        )
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")
        captured_queries: list[object] = []
        captured_configs: list[WritingStyleFetchConfig] = []
        captured_refine: list[tuple[object, dict[str, object]]] = []

        async def fake_fetch(
            query: object,
            config: WritingStyleFetchConfig | None = None,
        ) -> list[WritingStyleDocument]:
            captured_queries.append(query)
            if config is not None:
                captured_configs.append(config)
            return [doc] * 8

        async def fake_refine(question: object, **kwargs: object) -> list[str]:
            captured_refine.append((question, dict(kwargs)))
            return [f"head {i}" for i in range(1, 10)]

        monkeypatch.setattr(type(role), "afetch_document", staticmethod(fake_fetch))
        monkeypatch.setattr(type(role), "arefined_query", staticmethod(fake_refine))

        docs = await role._fetch_style_docs(ctx.description, ctx.rag, "story 'Battle'")

        assert docs == [doc] * 7
        assert captured_refine[0][0] == "The hero fights.\nquery guide"
        assert "k" not in captured_refine[0][1]  # the model decides how many heads to decompose into
        assert captured_queries == [[f"head {i}" for i in range(1, 8)]]  # heads beyond the limit are dropped
        assert captured_configs
        assert captured_configs[0].limit == 7

    async def test_fetch_style_docs_searches_the_given_text_alone(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert _fetch_style_docs decomposes the level's own text when no rag_query is set."""
        role = make_test_role(NovelCompose, RAGChapterCompose, name="rag_role")
        ctx = RagStoryContext(title="Battle", description="The hero fights.", rag=RagRetrieval())
        captured_queries: list[object] = []
        captured_refine: list[object] = []

        async def fake_fetch(
            query: object,
            config: WritingStyleFetchConfig | None = None,
        ) -> list[WritingStyleDocument]:
            captured_queries.append(query)
            return []

        async def fake_refine(question: object, **kwargs: object) -> list[str]:
            captured_refine.append(question)
            return ["a duel at dusk", "a quiet standoff"]

        monkeypatch.setattr(type(role), "afetch_document", staticmethod(fake_fetch))
        monkeypatch.setattr(type(role), "arefined_query", staticmethod(fake_refine))

        await role._fetch_style_docs(ctx.description, ctx.rag, "story 'Battle'")

        assert captured_refine == ["The hero fights."]
        assert captured_queries == [["a duel at dusk", "a quiet standoff"]]

    async def test_fetch_style_docs_skips_blank_prompt_docs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert docs whose prompt renders blank are filtered out."""
        role = make_test_role(NovelCompose, RAGChapterCompose, name="rag_role")
        ctx = RagStoryContext(title="Battle", description="The hero fights.", rag=RagRetrieval())
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")
        blank = WritingStyleDocument.with_text_chunk("   ")

        async def fake_fetch(
            query: object,
            config: WritingStyleFetchConfig | None = None,
        ) -> list[WritingStyleDocument]:
            return [blank, doc, blank]

        async def fake_refine(question: object, **kwargs: object) -> list[str]:
            return ["a duel at dusk", "a quiet standoff"]

        monkeypatch.setattr(type(role), "afetch_document", staticmethod(fake_fetch))
        monkeypatch.setattr(type(role), "arefined_query", staticmethod(fake_refine))

        docs = await role._fetch_style_docs(ctx.description, ctx.rag, "story 'Battle'")

        assert docs == [doc]

    async def test_fetch_style_docs_falls_back_to_raw_query(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert an empty decomposition still searches the raw story query instead of starving the prompt."""
        role = make_test_role(NovelCompose, RAGChapterCompose, name="rag_role")
        ctx = RagStoryContext(title="Battle", description="The hero fights.", rag=RagRetrieval())
        captured_queries: list[object] = []

        async def fake_fetch(
            query: object,
            config: WritingStyleFetchConfig | None = None,
        ) -> list[WritingStyleDocument]:
            captured_queries.append(query)
            return []

        async def fake_refine(question: object, **kwargs: object) -> list[str]:
            return []

        monkeypatch.setattr(type(role), "afetch_document", staticmethod(fake_fetch))
        monkeypatch.setattr(type(role), "arefined_query", staticmethod(fake_refine))

        await role._fetch_style_docs(ctx.description, ctx.rag, "story 'Battle'")

        assert captured_queries == [["The hero fights."]]

    async def test_fetch_style_docs_discards_a_lone_head(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert a one-head answer — here a refusal — is discarded for the raw question, not searched."""
        role = make_test_role(NovelCompose, RAGChapterCompose, name="rag_role")
        ctx = RagStoryContext(title="Battle", description="The hero fights.", rag=RagRetrieval())
        captured_queries: list[object] = []

        async def fake_fetch(
            query: object,
            config: WritingStyleFetchConfig | None = None,
        ) -> list[WritingStyleDocument]:
            captured_queries.append(query)
            return []

        async def fake_refine(question: object, **kwargs: object) -> list[str]:
            return ["Sorry, I cannot help generate or optimize queries of this nature."]

        monkeypatch.setattr(type(role), "afetch_document", staticmethod(fake_fetch))
        monkeypatch.setattr(type(role), "arefined_query", staticmethod(fake_refine))

        await role._fetch_style_docs(ctx.description, ctx.rag, "story 'Battle'")

        assert captured_queries == [["The hero fights."]]

    async def test_rag_settings_survive_story_composition(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert retrieval settings set on the story survive composition and scenes stay RAG-free."""
        role = make_test_role(NovelCompose, RAGChapterCompose, name="rag_role")
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval(query="guide", limit=7))

        async def fake_fetch(
            query: object,
            config: WritingStyleFetchConfig | None = None,
        ) -> list[WritingStyleDocument]:
            return []

        async def fake_refine(question: object, **kwargs: object) -> list[str]:
            return ["the departure", "a cold platform"]

        monkeypatch.setattr(type(role), "afetch_document", staticmethod(fake_fetch))
        monkeypatch.setattr(type(role), "arefined_query", staticmethod(fake_refine))
        with MockScript.from_values(
            Value.from_json(
                [
                    {
                        "title": "S1",
                        "description": "Leaving home.",
                        "weight": 1.0,
                        "writing_styles": [],
                        "writing_constraints": [],
                    }
                ],
                name="scene plans",
            ),
            Value.from_generic("He left.", name="scene prose"),
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
        assert isinstance(novel.child_contexts[0], RagChapterContext)
        assert novel.child_contexts[0].child_contexts[0].rag == RagRetrieval(query="guide", limit=3)

    async def test_seal_carries_character_spans_into_scene_planning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert sealing keeps the roster's state cards on the story and in its scene-planning prompt."""
        role = make_test_role(NovelCompose, RAGChapterCompose, name="rag_role")
        plan = StoryPlan(
            title="St1",
            description="The departure.",
            weight=1.0,
            writing_styles=[],
            writing_constraints=[],
            cast=["Hero"],
        )
        story = StoryContext(title="St1", description="The departure.", expected_word_count=100)
        story.update_from(plan).set_plan(plan)
        story.set_charactor_spans([CharacterSpan(start=card("Hero"), end=card("Hero", look="wounded"))])
        story.set_language("English")
        story.set_outline("The hero seeks his father.")
        captured: list[str] = []

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> None:
            captured.append(requirement)

        monkeypatch.setattr(type(role), "propose", staticmethod(fake_propose))

        sealed = RagStoryContext.seal(story, RagRetrieval(query="guide", limit=3))

        assert sealed.charactor_span == story.charactor_span
        assert sealed.language == "English"
        assert sealed.outline == "The hero seeks his father."

        await role.plan_scenes(sealed)

        assert captured
        assert "Initial State:" in captured[0]
        assert "wounded" in captured[0]

    async def test_fully_written_story_stops_seeding_scene_prefixes(self) -> None:
        """Assert the reference entry renders while a scene is unwritten and stops once every scene carries content."""
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval())
        story.add_retrieved_styles(["Dark gothic prose with terse action lines."])
        story.add_context(
            SceneContext(title="S1", description="Leaving home.", expected_word_count=50).set_content("He left.")
        )
        unwritten = SceneContext(title="S2", description="The road.", expected_word_count=50)
        story.add_context(unwritten)

        while_writing = [entry.kind for scene in story.iter_prefixed_contexts() for entry in scene.prefix_log.entries]
        assert while_writing == ["style_references", "style_references", "scene_content"]

        unwritten.set_content("He walked.")
        scenes = list(story.iter_prefixed_contexts())

        assert story.prefixed_header_entry() is None
        assert [entry.kind for entry in scenes[0].prefix_log.entries] == []
        assert [entry.kind for entry in scenes[1].prefix_log.entries] == ["scene_content"]
        assert story.retrieved_styles == ["Dark gothic prose with terse action lines."]

    async def test_compose_story_stops_rendering_docs_once_scenes_written(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert a fully written story stops rendering its retrieved docs while keeping the raw texts."""
        role = make_test_role(NovelCompose, RAGChapterCompose, name="rag_role")
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval(query="guide", limit=7))
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")

        async def fake_fetch(
            query: object,
            config: WritingStyleFetchConfig | None = None,
        ) -> list[WritingStyleDocument]:
            return [doc]

        async def fake_refine(question: object, **kwargs: object) -> list[str]:
            return ["the departure"]

        monkeypatch.setattr(type(role), "afetch_document", staticmethod(fake_fetch))
        monkeypatch.setattr(type(role), "arefined_query", staticmethod(fake_refine))
        with MockScript.from_values(
            Value.from_json(
                [
                    {
                        "title": "S1",
                        "description": "Leaving home.",
                        "weight": 1.0,
                        "writing_styles": [],
                        "writing_constraints": [],
                    }
                ],
                name="scene plans",
            ),
            Value.from_text("He left.", name="scene prose"),
        ):
            result = await role.compose_story(story)

        assert result is not None
        assert story.retrieved_styles == [doc.as_prompt()]
        assert story.prefixed_header_entry() is None
        assert all(
            entry.kind != "style_references"
            for scene in story.iter_prefixed_contexts()
            for entry in scene.prefix_log.entries
        )

    async def test_staged_compose_stops_rendering_docs_of_written_story(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert RagComposeScenesStage stops rendering a fully written story's retrieved docs."""
        from fabricatio_novel.actions.novel import RagComposeScenesStage
        from fabricatio_novel.capabilities.story import StoryCompose

        async def fake_compose(
            self: StoryCompose, ctx: StoryContext, send_to: str | None = None, **kwargs: object
        ) -> bool:
            for scene_ctx in ctx.child_contexts:
                scene_ctx.set_content("He left.")
            return True

        monkeypatch.setattr(StoryCompose, "compose_scenes_phase", fake_compose)
        stage = RagComposeScenesStage()
        novel = NovelContext.create("The hero seeks his father.", language="English")
        chapter = RagChapterContext(title="Ch1", description="The start.", expected_word_count=100)
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval())
        story.add_retrieved_styles(["Dark gothic prose with terse action lines."])
        scene = SceneContext(title="S1", description="Leaving home.", expected_word_count=50)
        scene.set_plan(
            ScenePlan(title="S1", description="Leaving home.", weight=1.0, writing_styles=[], writing_constraints=[])
        )
        story.add_context(scene)
        chapter.add_context(story)
        novel.add_context(chapter)

        assert await stage._execute(novel) is True

        assert story.retrieved_styles == ["Dark gothic prose with terse action lines."]
        assert story.prefixed_header_entry() is None
        assert all(
            entry.kind != "style_references"
            for scene_ctx in story.iter_prefixed_contexts()
            for entry in scene_ctx.prefix_log.entries
        )

    async def test_staged_compose_keeps_docs_when_story_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert a story that fails mid-write keeps its retrieved docs for the retry and snapshot."""
        from fabricatio_novel.actions.novel import RagComposeScenesStage
        from fabricatio_novel.capabilities.story import StoryCompose

        async def fake_compose(
            self: StoryCompose, ctx: StoryContext, send_to: str | None = None, **kwargs: object
        ) -> bool:
            return False

        monkeypatch.setattr(StoryCompose, "compose_scenes_phase", fake_compose)
        stage = RagComposeScenesStage()
        novel = NovelContext.create("The hero seeks his father.", language="English")
        chapter = RagChapterContext(title="Ch1", description="The start.", expected_word_count=100)
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval())
        story.add_retrieved_styles(["Dark gothic prose with terse action lines."])
        story.add_context(SceneContext(title="S1", description="Leaving home.", expected_word_count=50))
        chapter.add_context(story)
        novel.add_context(chapter)

        assert await stage._execute(novel) is False

        assert story.prefixed_header_entry() is not None
        assert any(
            entry.kind == "style_references"
            for scene_ctx in story.iter_prefixed_contexts()
            for entry in scene_ctx.prefix_log.entries
        )

    async def test_rendering_state_survives_snapshot_round_trip(self) -> None:
        """Assert a reloaded tree renders what the run rendered: docs while a scene is unwritten, none once all are."""
        novel = NovelContext.create("The hero seeks his father.", language="English")
        chapter = RagChapterContext(title="Ch1", description="The start.", expected_word_count=100)
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval())
        story.add_retrieved_styles(["Dark gothic prose with terse action lines."])
        story.add_context(
            SceneContext(title="S1", description="Leaving home.", expected_word_count=50).set_content("He left.")
        )
        unwritten = SceneContext(title="S2", description="The road.", expected_word_count=50)
        story.add_context(unwritten)
        chapter.add_context(story)
        novel.add_context(chapter)

        reloaded = RagNovelContext.model_validate(novel.model_dump())
        reloaded_story = reloaded.child_contexts[0].child_contexts[0]

        assert reloaded_story.retrieved_styles == ["Dark gothic prose with terse action lines."]
        assert any(
            entry.kind == "style_references"
            for scene in reloaded_story.iter_prefixed_contexts()
            for entry in scene.prefix_log.entries
        )

        reloaded_story.child_contexts[1].set_content("He walked.")

        assert reloaded_story.prefixed_header_entry() is None
        assert all(
            entry.kind != "style_references"
            for scene in reloaded_story.iter_prefixed_contexts()
            for entry in scene.prefix_log.entries
        )


class TestRAGNovelCompose:
    """Test suite for the novel-level (outline) writing style retrieval."""

    async def test_init_stage_seals_the_root_and_searches_the_outline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert the RAG init stage seals the root with its settings, searches the outline, and snapshots it."""
        from fabricatio_novel.actions.novel import RagInitNovelContext

        stage = RagInitNovelContext(rag_query="terse prose", rag_limit=2)
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")
        refined: list[object] = []
        fetched: list[object] = []

        async def fake_refine(question: object, **kwargs: object) -> list[str]:
            refined.append(question)
            return ["a duel at dusk", "a quiet standoff"]

        async def fake_fetch(query: object, config: object | None = None) -> list[WritingStyleDocument]:
            fetched.append(query)
            return [doc]

        monkeypatch.setattr(type(stage), "arefined_query", staticmethod(fake_refine))
        monkeypatch.setattr(type(stage), "afetch_document", staticmethod(fake_fetch))

        ctx = await stage._execute(
            novel_outline="The hero seeks his father.",
            novel_language="English",
            persist_dir=tmp_path,
        )

        assert isinstance(ctx, RagNovelContext)
        assert ctx.rag == RagRetrieval(query="terse prose", limit=2)
        assert ctx.style_references() == [doc.as_prompt()]
        assert ctx.language == "English"
        assert refined == ["The hero seeks his father.\nterse prose"]
        assert fetched == [["a duel at dusk", "a quiet standoff"]]

        (snapshot,) = (tmp_path / "stage_01_init").glob("RagNovelContext_*.json")
        reloaded = RagNovelContext.model_validate_json(snapshot.read_text(encoding="utf-8"))

        assert reloaded.style_references() == [doc.as_prompt()]
        assert reloaded.rag == RagRetrieval(query="terse prose", limit=2)

    async def test_sealed_root_renders_its_references_into_both_planning_prompts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert the novel's references reach the metadata proposal and the chapter planning prompts."""
        role = make_test_role(RAGNovelCompose, name="rag_novel_role")
        novel = RagNovelContext(
            title="The Atlas", description="An apprentice maps a drifting city.", outline="Outline."
        )
        novel.add_retrieved_styles(["Dark gothic prose."])
        captured: list[str] = []

        async def fake_propose(model: object, requirement: str, *args: object, **kwargs: object) -> None:
            captured.append(requirement)

        monkeypatch.setattr(type(role), "propose", staticmethod(fake_propose))

        await role.propose_novel_metadata(novel)
        await role.plan_chapters(novel)

        metadata_prompt, chapter_prompt = captured
        for prompt in (metadata_prompt, chapter_prompt):
            assert "Retrieved Writing Style References" in prompt
            assert "Dark gothic prose." in prompt

    async def test_plain_novel_prompts_carry_no_references_section(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert a run without retrieval renders no references section in either planning prompt."""
        role = make_test_role(NovelCompose, name="plain_novel_role")
        novel = NovelContext.create("The hero seeks his father.", language="English")
        captured: list[str] = []

        async def fake_propose(model: object, requirement: str, *args: object, **kwargs: object) -> None:
            captured.append(requirement)

        monkeypatch.setattr(type(role), "propose", staticmethod(fake_propose))

        await role.propose_novel_metadata(novel)
        await role.plan_chapters(novel)

        assert len(captured) == 2
        assert all("Retrieved Writing Style References" not in prompt for prompt in captured)

    async def test_planning_chapters_leaves_them_the_rag_chapter_type(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert the RAG chapter planning phase promotes the chapters it plans onto the RAG chapter type."""
        from fabricatio_novel.actions.novel import RagPlanChaptersStage

        stage = RagPlanChaptersStage()
        novel = RagNovelContext(title="The Atlas", description="A drifting city.", outline="Outline.")

        async def fake_plan_chapters(
            ctx: NovelContext, send_to: str | None = None, **kwargs: object
        ) -> list[ChapterPlan]:
            return [
                ChapterPlan(
                    title="Ch1",
                    description="The apprentice boards the ferry barge.",
                    weight=1.0,
                    writing_styles=[],
                    writing_constraints=[],
                )
            ]

        monkeypatch.setattr(type(stage), "plan_chapters", staticmethod(fake_plan_chapters))

        assert await stage.plan_chapters_phase(novel) is True

        assert [chapter.title for chapter in novel.child_contexts] == ["Ch1"]
        assert all(isinstance(chapter, RagChapterContext) for chapter in novel.child_contexts)

    def test_rag_accessors_are_not_shadowed_by_the_plain_default(self) -> None:
        """Assert both RAG levels answer style_references from their own state, not the plain empty default."""
        story = RagStoryContext(title="St1", description="The departure.", rag=RagRetrieval())
        story.add_retrieved_styles(["Style A."])
        novel = RagNovelContext(title="The Atlas", description="A drifting city.", outline="Outline.")
        novel.add_retrieved_styles(["Style B."])

        assert story.style_references() == ["Style A."]
        assert novel.style_references() == ["Style B."]

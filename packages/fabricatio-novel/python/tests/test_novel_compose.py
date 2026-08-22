"""Composition-chain tests for fabricatio-novel with mock LLM routers."""

from typing import List

import pytest
from _support import NovelRole, card, prefix_log, raw_value
from fabricatio_mock.models.mock_router import Value, return_mixed_router_usage, return_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.models.context.base import CharacterSpan
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import NovelPlan, ScenePlan
from fabricatio_novel.models.series_book import SeriesBible


class TestCharacterSpans:
    """Test suite for the per-level CharacterSpan pipeline."""

    async def test_compose_novel_stitches_chapter_boundaries_to_roster_ends(self) -> None:
        """Assert N chapters need N-1 boundary cards; chapter 1 starts at the novel start and the last ends at the novel end."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        bible = SeriesBible(characters=["Hero — brave protagonist."])
        ctx.set_series_bible(bible)
        meta = NovelPlan(
            title="The Search", description="A hero searching.", expected_word_count=100, series_bible=bible
        )
        novel_start = card()
        novel_end = novel_start.model_copy(update={"look": "wounded"})
        chapter_boundary = novel_start.model_copy(update={"act": "cautious"})
        chapter_plans_json = [
            {"title": "Ch1", "description": "The start.", "weight": 1.0},
            {"title": "Ch2", "description": "The road.", "weight": 1.0},
        ]
        story_plans_json = [{"title": "St1", "description": "The departure.", "weight": 1.0}]
        scene_plans_json = [{"title": "S1", "description": "Leaving home.", "weight": 1.0}]
        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                Value([CharacterSpan(start=novel_start, end=novel_end).model_dump()], "json"),
                Value(chapter_plans_json, "json"),
                # 2 chapters -> 1 boundary card per roster character
                Value([[chapter_boundary.model_dump()]], "json"),
                Value(story_plans_json, "json"),
                Value(scene_plans_json, "json"),
                raw_value("He left."),
                Value(story_plans_json, "json"),
                Value(scene_plans_json, "json"),
                raw_value("He walked."),
            )
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert len(ctx.charactor_span) == 1
        assert ctx.charactor_span[0].start.name == "Hero"
        assert ctx.charactor_span[0].end.look == "wounded"
        # chapter 1 opens at the novel start and closes at the boundary
        ch1 = ctx.chapter_context[0]
        assert len(ch1.charactor_span) == 1
        assert ch1.charactor_span[0].start.look == "tall"
        assert ch1.charactor_span[0].end.act == "cautious"
        # chapter 2 opens at the boundary and closes at the novel end
        ch2 = ctx.chapter_context[1]
        assert len(ch2.charactor_span) == 1
        assert ch2.charactor_span[0].start.act == "cautious"
        assert ch2.charactor_span[0].end.look == "wounded"
        # a single story inherits the chapter span directly, and scenes broadcast it
        story_ctx = ch1.story_context[0]
        assert story_ctx.charactor_span is ch1.charactor_span
        scene_ctx = story_ctx.scene_context[0]
        assert scene_ctx.charactor_span is ch1.charactor_span
        requirement = await role.prepare_scene_requirement(scene_ctx)
        assert "Initial State:" in requirement
        assert "finalizing State:" in requirement
        assert "## Act" in requirement
        assert "cautious" in requirement

    async def test_draft_chapter_spans_single_chapter_inherits_roster(self) -> None:
        """Assert a single chapter gets the roster spans directly without an LLM call."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero.", language="English")
        span = CharacterSpan(start=card(), end=card())
        ctx.set_charactor_spans([span])
        ctx.add_chapter_context(ChapterContext(title="Ch1", description="The start."))
        await role.draft_chapter_spans(ctx)
        assert ctx.chapter_context[0].charactor_span is ctx.charactor_span

    async def test_draft_story_spans_single_story_inherits_chapter_span(self) -> None:
        """Assert a single story gets the chapter's spans directly without an LLM call."""
        role = NovelRole(name="novel_role")
        chapter = ChapterContext(title="Ch1", description="The start.")
        span = CharacterSpan(start=card(), end=card())
        chapter.set_charactor_spans([span])
        chapter.add_story_context(StoryContext(title="St1", description="The departure."))
        await role.draft_story_spans(chapter)
        assert chapter.story_context[0].charactor_span is chapter.charactor_span

    async def test_scene_requirement_shows_character_span(self) -> None:
        """Assert the scene prompt renders the broadcast span's start and end."""
        role = NovelRole(name="novel_role")
        start = card()
        end = card().model_copy(update={"look": "scarred"})
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.set_charactor_spans([CharacterSpan(start=start, end=end)])
        requirement = await role.prepare_scene_requirement(ctx)
        assert "Initial State:" in requirement
        assert "finalizing State:" in requirement
        assert "## Look" in requirement
        assert "scarred" in requirement

    def test_cast_missing_spans_reports_unknown_members(self) -> None:
        """Assert an uncovered cast member is reported as missing."""
        ctx = StoryContext(title="St1", description="D")
        ctx.set_cast(["Hero", "Ghost"])
        ctx.set_charactor_spans([CharacterSpan(start=card(), end=card())])
        assert ctx.cast_missing_spans() == ["Ghost"]

    def test_cast_missing_spans_empty_when_covered(self) -> None:
        """Assert a fully covered cast passes the roster check."""
        ctx = StoryContext(title="St1", description="D")
        ctx.set_cast(["Hero"])
        ctx.set_charactor_spans([CharacterSpan(start=card(), end=card())])
        assert ctx.cast_missing_spans() == []


class TestNovelCompose:
    """Test suite for the generation chain with mock LLM."""

    async def test_compose_scene_writes_content_back_to_context(self) -> None:
        """Assert compose_scene writes the generated scene content back to the context."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="Departure", description="The hero leaves home.", expected_word_count=50)
        with install_router_usage(*return_router_usage("He walked out.")):
            scene = await role.compose_scene(ctx)
        assert scene is not None
        assert scene.content == "He walked out."
        assert scene.expected_word_count == 50
        assert ctx.content == "He walked out."

    async def test_compose_novel_broadcasts_story_span_to_scenes(self) -> None:
        """Assert every scene inherits the story's spans when prepare_scene_write runs."""
        role = NovelRole(name="novel_role")
        story = StoryContext(title="St1", description="The departure.")
        span = CharacterSpan(start=card(), end=card())
        story.set_charactor_spans([span])
        scene_ctx = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)
        story.scene_context.append(scene_ctx)
        with install_router_usage(*return_router_usage("He fought.")):
            await role.prepare_scene_write(story)
            scene = await role.compose_scene(scene_ctx)
        assert scene is not None
        assert scene_ctx.charactor_span is story.charactor_span
        assert scene_ctx.charactor_span == [span]

    async def test_compose_novel_end_to_end(self) -> None:
        """Assert a full composition fills content and prefixes across a prefilled tree."""
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
                raw_value("He left."),
                raw_value("A stranger appeared."),
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
        chapter_header = "# Ch1\n\n> The hero sets out."
        scenes = ctx.chapter_context[0].story_context[0].scene_context
        assert scenes[0].prefix_log.render() == chapter_header
        assert scenes[0].scenes_log.render() == ""
        assert scenes[1].prefix_log.render() == chapter_header
        assert scenes[1].scenes_log.render() == "He left."

    async def test_compose_novel_logs_progress_per_level(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Assert composition emits per-level progress and completion log lines."""
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
                raw_value("He left."),
                raw_value("A stranger appeared."),
            )
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        err = capfd.readouterr().err
        assert "Generating novel from outline" in err
        assert "Novel plan proposed: 'The Search'" in err
        assert "Composing chapter 1/1 'Ch1'" in err
        assert "Composing story 1/1 'St1'" in err
        assert "Composing scene 1/2 'S1'" in err
        assert "Composing scene 2/2 'S2'" in err
        assert "Scene 'S1' composed" in err
        assert "Chapter 'Ch1' composed" in err
        assert "Novel 'The Search' composed" in err

    async def test_compose_novel_returns_none_when_metadata_fails(self) -> None:
        """Assert compose_novel returns None when metadata generation fails."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero.", language="English")
        with install_router_usage("not valid json", "", ""):
            novel = await role.compose_novel(ctx)
        assert novel is None

    async def test_prepare_scene_requirement_renders_prefixed_content_after_static_head(self) -> None:
        """Assert the static head leads and prefixed content renders after the Previous Content marker."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.set_prefix_log(prefix_log("He walked into the dark.", title="S2"))

        requirement = await role.prepare_scene_requirement(ctx)

        # the static head (incl. per-run language) leads so it stays prefix-cacheable
        assert requirement.startswith("# Scene Writing")
        assert requirement.index("Respond entirely in") < requirement.index("# Previous Content")
        assert requirement.index("He walked into the dark.") > requirement.index("# Previous Content")
        assert requirement.index("A stranger appears.") > requirement.index("## Scene")
        # the per-scene word count must not sit inside the static Requirements block
        assert requirement.index("Write approximately 50 words.") > requirement.index("Respond entirely in")

    async def test_prepare_scene_requirement_renders_writing_style(self) -> None:
        """Assert shared styles render mid-prompt and the scene's own style sits inside ## Scene."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.set_writing_styles(["Terse action lines, present tense, close third person."])
        ctx.set_scene_plan(
            ScenePlan(title="S2", description="A stranger appears.", writing_style="Close first person.")
        )
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Writing Styles" in requirement
        assert "Terse action lines, present tense, close third person." in requirement
        assert requirement.index("## Writing Styles") < requirement.index("## Scene")
        assert requirement.index("- Style: Close first person.") > requirement.index("## Scene")

    async def test_prepare_scene_requirement_skips_writing_style_when_empty(self) -> None:
        """Assert an unset writing style renders no style section."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Writing Styles" not in requirement
        assert "- Style:" not in requirement

    async def test_prepare_scene_requirement_renders_writing_constraint(self) -> None:
        """Assert the scene's accumulated writing constraint guides the prose requirement."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.writing_constraint = "First person view throughout."
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Writing Constraint" in requirement
        assert "First person view throughout." in requirement
        assert requirement.index("## Writing Constraint") > requirement.index("## Scene")

    async def test_prepare_scene_requirement_skips_writing_constraint_when_empty(self) -> None:
        """Assert an unset writing constraint renders no constraint section."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Writing Constraint" not in requirement

    async def test_scene_requirement_renders_cast(self) -> None:
        """Assert the scene's cast renders as an on-stage roster in the prose requirement."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.set_cast(["Hero", "Villain"])
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Cast" in requirement
        assert "Hero, Villain" in requirement

    async def test_scene_requirement_omits_cast_when_empty(self) -> None:
        """Assert an empty cast renders no cast section."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Cast" not in requirement

    async def test_plan_scenes_renders_story_cast(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert scene planning sees the story's cast as context."""
        role = NovelRole(name="novel_role")
        story = StoryContext(title="St1", description="The departure.")
        story.set_cast(["Hero", "Villain"])
        captured: List[str] = []

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> None:
            captured.append(requirement)

        monkeypatch.setattr(NovelRole, "propose", staticmethod(fake_propose))
        await role.plan_scenes(story)

        assert captured
        assert "## Story Cast" in captured[0]
        assert "Hero, Villain" in captured[0]

    async def test_plan_stories_renders_chapter_cast(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert story planning sees the chapter's cast as context."""
        role = NovelRole(name="novel_role")
        chapter = ChapterContext(title="Ch1", description="The start.")
        chapter.set_cast(["Hero"])
        captured: List[str] = []

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> None:
            captured.append(requirement)

        monkeypatch.setattr(NovelRole, "propose", staticmethod(fake_propose))
        await role.plan_stories(chapter)

        assert captured
        assert "## Chapter Cast" in captured[0]
        assert "Hero" in captured[0]


class TestPrefixAccumulation:
    """Test suite for prefix log dependency injection across levels."""

    def _scene_ctx(self, title: str, description: str) -> SceneContext:
        return SceneContext(title=title, description=description, expected_word_count=20)

    async def test_compose_story_injects_prefix_across_scenes(self) -> None:
        """Assert later scenes accumulate earlier scene content into scenes_so_far."""
        role = NovelRole(name="novel_role")
        story = StoryContext(title="St1", description="The departure.")
        scene_1 = self._scene_ctx("S1", "Leaving home.")
        scene_2 = self._scene_ctx("S2", "A stranger appears.")
        story.add_scene_context(scene_1).add_scene_context(scene_2)
        with install_router_usage(
            *return_router_usage(
                "He left.",
                "A stranger appeared.",
            )
        ):
            result = await role.compose_story(story)
        assert result is not None
        assert scene_1.prefix_log.render() == ""
        assert scene_1.scenes_log.render() == ""
        assert scene_2.prefix_log.render() == ""
        assert scene_2.scenes_log.render() == "He left."

    async def test_compose_chapter_injects_prefix_across_stories(self) -> None:
        """Assert stories inherit the chapter header plus prior story blocks as prefixed_content."""
        role = NovelRole(name="novel_role")
        chapter = ChapterContext(title="Ch1", description="The start.")
        story_a = StoryContext(title="StA", description="A.")
        story_a.add_scene_context(self._scene_ctx("S1", "Leaving home."))
        story_b = StoryContext(title="StB", description="B.")
        story_b.add_scene_context(self._scene_ctx("S2", "A stranger appears."))
        chapter.add_story_context(story_a).add_story_context(story_b)
        with install_router_usage(
            *return_router_usage(
                "Alpha.",
                "Beta.",
            )
        ):
            result = await role.compose_chapter(chapter)
        assert result is not None
        story_a_block = "Alpha."
        chapter_header = "# Ch1\n\n> The start."
        assert story_a.prefix_log.render() == chapter_header
        assert story_b.prefix_log.render() == f"{chapter_header}\n\n{story_a_block}"
        assert story_b.scene_context[0].prefix_log.render() == f"{chapter_header}\n\n{story_a_block}"

    async def test_compose_novel_injects_prefix_across_chapters_and_stories(self) -> None:
        """Assert chapter and story prefixed_content chain across the whole composed novel."""
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
                raw_value("A."),
                raw_value("B."),
                raw_value("C."),
                raw_value("D."),
            )
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        chapter_1_block = "# Ch1\n\n> The start.\n\nA.\n\nB."
        chapter_1_header = "# Ch1\n\n> The start."
        chapter_2_header = "# Ch2\n\n> The road."
        story_c_block = "C."
        assert chapter_1.prefix_log.render() == ""
        assert chapter_2.prefix_log.render() == chapter_1_block
        assert chapter_1.story_context[1].prefix_log.render() == f"{chapter_1_header}\n\nA."
        assert chapter_2.story_context[0].prefix_log.render() == f"{chapter_1_block}\n\n{chapter_2_header}"
        assert (
            chapter_2.story_context[1].prefix_log.render()
            == f"{chapter_1_block}\n\n{chapter_2_header}\n\n{story_c_block}"
        )
        assert (
            chapter_2.story_context[0].scene_context[0].prefix_log.render()
            == f"{chapter_1_block}\n\n{chapter_2_header}"
        )
        assert (
            chapter_2.story_context[1].scene_context[0].prefix_log.render()
            == f"{chapter_1_block}\n\n{chapter_2_header}\n\n{story_c_block}"
        )
